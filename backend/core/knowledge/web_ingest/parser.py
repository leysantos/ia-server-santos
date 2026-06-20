"""Extrai links de download de páginas HTML."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, unquote

from core.knowledge.ingestion import INGESTABLE_SUFFIXES

_EXT_IN_TEXT = re.compile(r"(\.(docx|doc|pdf|xlsx|xls|csv))\b", re.I)
_ANCHOR_RE = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.I | re.S,
)
_BAIXAR_RE = re.compile(r"\b(baixar|download|visualizar)\b", re.I)
_GENERIC_ROW_LABELS = frozenset({
    "instrução técnica",
    "norma técnica",
    "norma administrativa",
    "lei",
    "decreto",
    "portaria",
    "parecer",
    "atas de comissão técnica",
    "baixar",
    "download",
    "visualizar",
    "sim",
    "não",
    "nao",
    "---",
    "-",
    "",
})


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._current_href:
            return
        label = " ".join(self._current_text).strip()
        self.links.append((self._current_href, label))
        self._current_href = None
        self._current_text = []


def _suffix_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    query = urlparse(url).query.lower()
    for part in (path, query):
        match = _EXT_IN_TEXT.search(part)
        if match:
            return match.group(1).lower()
    if "." in path:
        return "." + path.rsplit(".", 1)[-1]
    return ""


def _suffix_from_label(label: str) -> str:
    match = _EXT_IN_TEXT.search(label)
    return match.group(1).lower() if match else ""


def _clean_html(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", text).strip()


def _cell_texts(row_html: str) -> list[str]:
    return [_clean_html(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.I | re.S)]


def _compose_row_label(cell_texts: list[str]) -> str:
    """Monta rótulo legível a partir das colunas da linha (ex.: IT Nº 2/2019 - Assunto)."""
    if not cell_texts:
        return ""

    texts = [t.strip() for t in cell_texts if t and t.strip()]
    if not texts:
        return ""

    first = texts[0]
    # Tabelas CBMAM / legislação: Tipo | Nº | Ano | Vigência | Assunto | Anexos | Ação
    if len(texts) >= 5 and texts[1].isdigit():
        tipo = first
        numero = texts[1]
        ano = texts[2] if len(texts) > 2 and texts[2].isdigit() else ""
        assunto = texts[4] if len(texts) > 4 else ""
        if assunto.lower() not in _GENERIC_ROW_LABELS:
            head = f"{tipo} Nº {numero}"
            if ano:
                head += f"/{ano}"
            return f"{head} - {assunto}"

    for text in texts:
        if _suffix_from_label(text):
            return text

    meaningful = [t for t in texts if t.lower() not in _GENERIC_ROW_LABELS and not t.isdigit()]
    if meaningful:
        return max(meaningful, key=len)

    # Evita rótulos inúteis vindos de tabelas auxiliares (ex.: "70").
    if first.isdigit():
        return ""
    return first


def _guess_suffix_from_url(url: str, label: str) -> str:
    suffix = _suffix_from_url(url) or _suffix_from_label(label)
    if suffix in INGESTABLE_SUFFIXES:
        return suffix
    path = urlparse(url).path.lower()
    if any(token in path for token in ("/legislacaos/download/", "/download/", "/anexo-legislacaos/download/")):
        return ".pdf"
    return suffix


def _friendly_name(label: str, url: str, hint_suffix: str = "") -> str:
    cleaned = re.sub(r"\s+", " ", label).strip()
    if cleaned.isdigit():
        cleaned = ""
    if cleaned and cleaned.lower() not in {"baixar", "download", "anexo", "visualizar"}:
        return cleaned[:200]
    path = urlparse(url).path
    stem = unquote(path.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    # IDs numéricos em /download/70 não são nomes úteis para RAG.
    if (
        stem
        and not stem.isdigit()
        and stem.lower() not in {"download", "baixar", "arquivo", "file"}
    ):
        return stem.replace("-", " ").replace("_", " ")[:200]
    return f"documento{hint_suffix}" if hint_suffix else "documento"


def _find_anchors(fragment: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for href, inner in _ANCHOR_RE.findall(fragment):
        text = _clean_html(inner)
        results.append((href, text))
    return results


def _parse_hidden_fields(form_inner: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]+>", form_inner, re.I):
        if not re.search(r"""type\s*=\s*["']hidden["']""", tag, re.I):
            continue
        name_m = re.search(r"""name\s*=\s*["']([^"']+)["']""", tag, re.I)
        if not name_m:
            continue
        val_m = re.search(r"""value\s*=\s*["']([^"']*)["']""", tag, re.I)
        fields[name_m.group(1)] = val_m.group(1) if val_m else ""
    return fields


def _extract_post_form(fragment: str) -> tuple[str, dict[str, str]] | None:
    """Formulário POST oculto (ex.: CakePHP CBMAM: Baixar submete form com CSRF)."""
    form_match = re.search(
        r"""<form[^>]+action\s*=\s*["']([^"']+)["'][^>]*>(.*?)</form>""",
        fragment,
        re.I | re.S,
    )
    if not form_match:
        return None
    action = form_match.group(1).strip()
    if not action or action == "#":
        return None
    fields = _parse_hidden_fields(form_match.group(2))
    if not fields:
        return None
    return action, fields


def extract_download_links(
    html: str,
    page_url: str,
    *,
    max_links: int = 100,
) -> list[dict[str, str]]:
    """
    Retorna links de arquivos indexáveis encontrados na página.
    Suporta tabelas PSCIP/CBMAM: nome do anexo na 1ª coluna, Baixar na 2ª.
    """
    parser = _LinkParser()
    parser.feed(html)

    seen: set[tuple[str, str]] = set()
    candidates: list[dict[str, str | dict[str, str]]] = []

    def _add(
        url: str,
        label: str,
        score: int,
        hint_filename: str = "",
        hint_suffix: str = "",
        post_data: dict[str, str] | None = None,
        description: str = "",
    ) -> None:
        absolute = urljoin(page_url, url)
        effective_label = label or hint_filename
        dedupe_key = (absolute, hint_filename or effective_label)
        if dedupe_key in seen:
            return
        suffix = (
            _guess_suffix_from_url(absolute, effective_label)
            or hint_suffix
            or _suffix_from_label(effective_label)
        )
        if suffix and suffix not in INGESTABLE_SUFFIXES:
            return
        # Links "Baixar" sem extensão na URL — confiar no rótulo da linha (ex.: ANEXO A.docx)
        if not suffix and score < 4:
            return
        seen.add(dedupe_key)
        display = effective_label
        file_hint = hint_filename or effective_label
        if suffix and not file_hint.lower().endswith(suffix):
            file_hint = f"{file_hint}{suffix}"
        item: dict[str, str | dict[str, str]] = {
            "url": absolute,
            "label": display,
            "suffix": suffix,
            "score": str(score),
            "hint_filename": file_hint,
            "hint_suffix": suffix,
            "description": description or display,
        }
        if post_data:
            item["post_data"] = post_data
        candidates.append(item)

    # Tabelas: par nome do arquivo + link Baixar (portais gov/CBMAM)
    for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
        row_html = row_match.group(1)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.I | re.S)
        if not cells:
            continue

        cell_texts = _cell_texts(row_html)
        row_label = _compose_row_label(cell_texts)
        row_suffix = _suffix_from_label(row_label) or _guess_suffix_from_url("", row_label)
        row_has_form = False

        for cell_html in cells:
            form_info = _extract_post_form(cell_html)
            if not form_info:
                continue
            action, post_data = form_info
            guessed = _guess_suffix_from_url(urljoin(page_url, action), row_label)
            _add(
                action,
                row_label,
                10,
                hint_filename=row_label,
                hint_suffix=guessed or row_suffix,
                post_data=post_data,
                description=row_label,
            )
            row_has_form = True
            break

        if row_has_form:
            continue

        for cell_html in cells:
            for href, link_text in _find_anchors(cell_html):
                if href.strip() in ("", "#"):
                    continue
                is_download_action = bool(_BAIXAR_RE.search(link_text))
                # "Baixar/Download/Visualizar" sem rótulo de linha não serve (evita capturar tabelas irrelevantes).
                if is_download_action and not (row_label or row_suffix):
                    continue
                if is_download_action or row_suffix or row_label:
                    guessed = _guess_suffix_from_url(urljoin(page_url, href), row_label)
                    score = 9 if row_label and row_label.lower() not in _GENERIC_ROW_LABELS else 6
                    if _suffix_from_label(row_label):
                        score = 8
                    _add(
                        href,
                        row_label or link_text,
                        score,
                        hint_filename=row_label or link_text,
                        hint_suffix=guessed or row_suffix,
                        description=row_label or link_text,
                    )

    # Links soltos (fora de tabela) — só quando o rótulo do <a> traz extensão no texto.
    for href, label in parser.links:
        if href.strip() in ("", "#"):
            continue
        label_suffix = _suffix_from_label(label)
        if label_suffix in INGESTABLE_SUFFIXES:
            _add(href, label, 7, hint_filename=label, hint_suffix=label_suffix)
            continue
        suffix = _suffix_from_url(href)
        if suffix in INGESTABLE_SUFFIXES:
            _add(href, label, 6, hint_suffix=suffix)

    # Mesma URL pode aparecer na tabela (score alto) e no fallback (score baixo).
    # Mantém apenas a melhor ocorrência por URL absoluta.
    candidates.sort(key=lambda x: int(x["score"]), reverse=True)
    deduped: list[dict[str, str | dict[str, str]]] = []
    seen_urls: set[str] = set()
    for item in candidates:
        url = str(item["url"])
        if url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(item)

    results: list[dict[str, str | dict[str, str]]] = []
    for item in deduped[:max_links]:
        suffix = str(item.get("hint_suffix") or item.get("suffix") or "")
        entry: dict[str, str | dict[str, str]] = {
            "url": str(item["url"]),
            "name": _friendly_name(str(item["label"]), str(item["url"]), suffix),
            "hint_filename": str(item.get("hint_filename") or item["label"]),
            "hint_suffix": suffix,
            "description": str(item.get("description") or item["label"]),
        }
        if item.get("post_data"):
            entry["post_data"] = item["post_data"]  # type: ignore[assignment]
        results.append(entry)
    return results


def preview_download_links(html: str, page_url: str, *, max_links: int = 100) -> list[dict[str, str]]:
    """Lista links detectados sem baixar (debug/preview)."""
    return extract_download_links(html, page_url, max_links=max_links)
