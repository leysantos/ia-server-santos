"""Extração de título legível para NBR/NR/IT a partir de nome de arquivo ou 1ª página."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from memory.nbr_catalog import parse_nbr_code
from core.knowledge.norm_bulk.nr_catalog import nr_label, parse_nr_code

_YEAR = re.compile(r"^(19\d{2}|20\d{2})$")
_IT_LINE = re.compile(
    r"instru(?:ç|c)(?:ã|a)o\s+t(?:é|e)cnica\s+n(?:[º°o.]?\s*)?(\d+)\s*/\s*(\d{4})",
    re.IGNORECASE,
)


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _strip_leading_year_segment(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^[\-\–—:,]+\s*", "", text)
    parts = [p.strip() for p in re.split(r"[\-\–—]", text) if p.strip()]
    while parts and _YEAR.fullmatch(parts[0]):
        parts.pop(0)
    return _clean_spaces(" - ".join(parts)) if parts else _clean_spaces(text)


def extract_title_from_filename(
    filename: str,
    *,
    norm_kind: str = "NBR",
    norm_code: str | None = None,
) -> str | None:
    """Ex.: «NBR 6118 - 2014 - Projeto de Estruturas de Concreto.pdf»."""
    stem = Path(filename).stem
    stem = _clean_spaces(stem.replace("_", " "))

    if norm_kind == "NR" and norm_code:
        patterns = [
            rf"(?:NR[\s\-_]?(?:0)?{re.escape(norm_code.lstrip('0') or '0')})",
            rf"(?:Norma\s+Regulamentadora\s+{re.escape(norm_code)})",
        ]
        for pattern in patterns:
            match = re.search(pattern, stem, re.IGNORECASE)
            if not match:
                continue
            tail = _strip_leading_year_segment(stem[match.end() :])
            if len(tail) >= 3:
                return _clean_spaces(f"{nr_label(norm_code)} - {tail}")
        if " - " in stem:
            return stem

    code = norm_code or parse_nbr_code(stem)
    if code:
        iso_match = re.search(
            rf"(?:ABNT\s+)?NBR\s+ISO[\s\-/]*IEC[\s\-]*{re.escape(code)}",
            stem,
            re.IGNORECASE,
        )
        if iso_match:
            year_match = re.search(
                rf"ISO[\s\-/]*IEC[\s\-]*{re.escape(code)}\s+(\d{{4}})",
                stem,
                re.IGNORECASE,
            )
            year_suffix = f" ({year_match.group(1)})" if year_match else ""
            return _clean_spaces(f"NBR {code} - ISO/IEC {code}{year_suffix}")

        match = re.search(rf"NBR[\s\-_]?{re.escape(code)}", stem, re.IGNORECASE)
        if match:
            tail = _strip_leading_year_segment(stem[match.end() :])
            if len(tail) >= 4:
                return _clean_spaces(f"NBR {code} - {tail}")
        if re.search(rf"\b{re.escape(code)}\b", stem) and " - " in stem:
            return stem

    it_match = _IT_LINE.search(stem)
    if it_match:
        num, year = it_match.group(1), it_match.group(2)
        tail = _strip_leading_year_segment(stem[it_match.end() :])
        base = f"Instrução Técnica Nº {num}/{year}"
        return _clean_spaces(f"{base} - {tail}") if tail else base

    if re.search(r"instru(?:ç|c)(?:ã|a)o\s+t(?:é|e)cnica", stem, re.IGNORECASE):
        return stem

    return None


def extract_title_from_pdf_text(
    text: str,
    *,
    norm_kind: str = "NBR",
    norm_code: str | None = None,
    max_lines: int = 20,
) -> str | None:
    if not text:
        return None

    lines = [_clean_spaces(line) for line in text.splitlines() if _clean_spaces(line)]
    snippet = "\n".join(lines[:max_lines])

    it_match = _IT_LINE.search(snippet)
    if it_match:
        num, year = it_match.group(1), it_match.group(2)
        idx = it_match.end()
        tail_parts: list[str] = []
        for line in lines[max(0, lines.index(_clean_spaces(it_match.group(0))) if it_match.group(0) in lines else 0) + 1 : max_lines]:
            low = line.lower()
            if any(k in low for k in ("sumário", "sumario", "objetivo", "secretaria", "corpo de bombeiros")):
                break
            if len(line) >= 4:
                tail_parts.append(line)
            if len(tail_parts) >= 2:
                break
        tail = _clean_spaces(" ".join(tail_parts))
        base = f"Instrução Técnica Nº {num}/{year}"
        return _clean_spaces(f"{base} - {tail}") if tail else base

    code = norm_code or parse_nbr_code(snippet)
    if code:
        for line in lines[:max_lines]:
            if re.search(rf"NBR[\s\-_]?{re.escape(code)}", line, re.IGNORECASE):
                tail = re.sub(rf"(?i)NBR[\s\-_]?{re.escape(code)}", "", line)
                tail = _strip_leading_year_segment(tail)
                if len(tail) >= 6:
                    return _clean_spaces(f"NBR {code} - {tail}")
                # título na linha seguinte
                idx = lines.index(line)
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    if len(next_line) >= 6 and not re.match(r"^(ABNT|NBR|NR)\b", next_line, re.I):
                        return _clean_spaces(f"NBR {code} - {next_line}")

    if norm_kind == "NR" and norm_code:
        for line in lines[:max_lines]:
            if re.search(rf"NR[\s\-_]?0?{re.escape(norm_code.lstrip('0') or '0')}\b", line, re.I):
                tail = re.sub(r"(?i)NR[\s\-_]?0?\d+", "", line)
                tail = _strip_leading_year_segment(tail)
                if len(tail) >= 4:
                    return _clean_spaces(f"{nr_label(norm_code)} - {tail}")

    return None


def _read_first_page(path: Path, max_chars: int = 4000) -> str:
    if path.suffix.lower() != ".pdf":
        return ""
    try:
        from memory.pdf_indexer import PDFIndexer

        pages = PDFIndexer.extract_text(path)
        if not pages:
            return ""
        return (pages[0][1] or "")[:max_chars]
    except Exception:
        return ""


def extract_norm_display_name(
    path: Path,
    *,
    norm_kind: str,
    norm_code: str | None,
    first_page_text: str | None = None,
) -> str | None:
    from_name = extract_title_from_filename(
        path.name,
        norm_kind=norm_kind,
        norm_code=norm_code,
    )
    if from_name and len(from_name) > 12:
        return from_name

    if first_page_text is None:
        first_page_text = _read_first_page(path)

    from_pdf = extract_title_from_pdf_text(
        first_page_text or "",
        norm_kind=norm_kind,
        norm_code=norm_code,
    )
    if from_pdf:
        return from_pdf
    return from_name


def is_bare_norm_name(name: str, norm_code: str | None = None) -> bool:
    text = _clean_spaces(name)
    if re.fullmatch(r"NBR\s+\d{4,5}", text, re.I):
        return True
    if norm_code and re.fullmatch(rf"NBR\s+{re.escape(norm_code)}", text, re.I):
        return True
    if re.fullmatch(r"NR[\s\-_]?\d{1,2}", text, re.I):
        return True
    return False
