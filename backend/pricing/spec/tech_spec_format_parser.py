"""Interpreta diretrizes de formatação escritas no prompt da especificação técnica."""

from __future__ import annotations

import re
from typing import Any

_FONT_MAP: dict[str, str] = {
    "arial": "Arial",
    "calibri": "Calibri",
    "verdana": "Verdana",
    "tahoma": "Tahoma",
    "times": "Times New Roman",
    "times new roman": "Times New Roman",
    "times roman": "Times New Roman",
}

_FORMAT_LOG_LABELS: dict[str, str] = {
    "page_numbers": "Numeração de páginas",
    "page_number_position": "Posição da numeração",
    "font_family": "Fonte",
    "font_size": "Tamanho da fonte",
    "line_spacing": "Entrelinha",
    "text_align": "Alinhamento do texto",
    "margin_top_cm": "Margem superior",
    "margin_bottom_cm": "Margem inferior",
    "margin_left_cm": "Margem esquerda",
    "margin_right_cm": "Margem direita",
    "document_title": "Título do documento",
    "header_text": "Cabeçalho",
    "logo_text": "Logo",
}


def format_prompt_help() -> str:
    """Texto de ajuda exibido na UI — exemplos de diretrizes de formatação."""
    return (
        "Formatação (opcional, no mesmo prompt): "
        "número da página no canto inferior esquerdo/direito/centralizado; "
        "fonte Arial ou Times New Roman 11pt ou 12pt; "
        "entrelinha 1,5 ou dupla; texto justificado; "
        "margens 3cm; título centralizado; logo (Empresa X)."
    )


def parse_format_directives(prompt: str, fmt: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Aplica diretrizes de formatação encontradas no prompt. Retorna (fmt, logs)."""
    if not prompt.strip():
        return fmt, []

    lower = prompt.lower()
    out = dict(fmt)
    logs: list[str] = []

    def set_field(key: str, value: Any, label: str | None = None) -> None:
        out[key] = value
        logs.append(f"{label or _FORMAT_LOG_LABELS.get(key, key)}: {value}")

    if _wants_no_page_numbers(lower):
        out["page_numbers"] = False
        logs.append("Numeração de páginas desativada.")
    elif _wants_page_numbers(lower):
        out["page_numbers"] = True
        logs.append("Numeração de páginas ativada.")

    page_pos = _extract_page_number_position(lower)
    if page_pos:
        out["page_number_position"] = page_pos
        pos_label = {"left": "inferior esquerdo", "center": "inferior centralizado", "right": "inferior direito"}
        logs.append(f"Numeração de páginas: canto {pos_label.get(page_pos, page_pos)}.")

    font = _extract_font_family(lower)
    if font:
        set_field("font_family", font)

    size = _extract_font_size(lower)
    if size:
        set_field("font_size", size)

    spacing = _extract_line_spacing(lower)
    if spacing:
        set_field("line_spacing", spacing)

    align = _extract_text_align(lower)
    if align:
        set_field("text_align", align)

    margins = _extract_margins(lower)
    for key, value in margins.items():
        set_field(key, value)

    header = _extract_header_text(prompt)
    if header:
        set_field("header_text", header)

    return out, logs


def _wants_page_numbers(text: str) -> bool:
    if _wants_no_page_numbers(text):
        return False
    return bool(
        re.search(r"numera(c|ç)[aã]o", text)
        and re.search(r"p[aá]gina", text)
        or re.search(r"n[uú]mero\s+d[aeo]\s+p[aá]gina", text)
        or "page number" in text
        or re.search(r"p[aá]gina\s+no\s+(canto|rodap)", text)
        or re.search(r"rodap[eé].*p[aá]gina", text)
    )


def _wants_no_page_numbers(text: str) -> bool:
    return bool(
        re.search(r"sem\s+numera(c|ç)[aã]o", text)
        or re.search(r"sem\s+n[uú]mero\s+de\s+p[aá]gina", text)
        or "sem paginação" in text
    )


def _extract_page_number_position(text: str) -> str | None:
    if re.search(r"(inferior|rodap[eé]).{0,20}esquer", text) or re.search(r"esquerdo.{0,15}inferior", text):
        return "left"
    if re.search(r"(inferior|rodap[eé]).{0,20}direit", text) or re.search(r"direito.{0,15}inferior", text):
        return "right"
    if (
        re.search(r"(inferior|rodap[eé]).{0,20}centr", text)
        or re.search(r"centr(alizad)?[oa].{0,15}(inferior|rodap)", text)
        or re.search(r"p[aá]gina\s+centr", text)
    ):
        return "center"
    return None


def _extract_font_family(text: str) -> str | None:
    for alias, canonical in sorted(_FONT_MAP.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return canonical
    m = re.search(
        r"(?:fonte|tipo\s+de\s+fonte|usar\s+fonte)\s*[:\-]?\s*([a-záàâãéêíóôõúç0-9\s]{3,30})",
        text,
        re.I,
    )
    if m:
        raw = m.group(1).strip().lower()
        for alias, canonical in sorted(_FONT_MAP.items(), key=lambda x: -len(x[0])):
            if alias in raw:
                return canonical
    return None


def _extract_font_size(text: str) -> int | None:
    m = re.search(r"(?:fonte|tamanho(?:\s+da\s+fonte)?)\s*[:\-]?\s*(\d{1,2})\s*(?:pt|pontos?)?", text, re.I)
    if m:
        size = int(m.group(1))
        if 8 <= size <= 18:
            return size
    m = re.search(r"\b(\d{1,2})\s*pt\b", text, re.I)
    if m:
        size = int(m.group(1))
        if 8 <= size <= 18:
            return size
    return None


def _extract_line_spacing(text: str) -> float | None:
    if re.search(r"entrelinha\s+dupla|espa[cç]amento\s+duplo|linha\s+dupla", text):
        return 2.0
    if re.search(r"entrelinha\s+simples|espa[cç]amento\s+simples|linha\s+simples", text):
        return 1.0
    m = re.search(r"(?:entrelinha|espa[cç]amento(?:\s+entre\s+linhas)?)\s*[:\-]?\s*(\d(?:[.,]\d+)?)", text)
    if m:
        return float(m.group(1).replace(",", "."))
    if re.search(r"entrelinha\s+1[,.]5|1[,.]5\s+de\s+entrelinha", text):
        return 1.5
    return None


def _extract_text_align(text: str) -> str | None:
    if re.search(r"\bjustificad", text) or "texto justificado" in text:
        return "justify"
    if re.search(r"alinhad[oa]s?\s+(?:a\s+)?esquerda", text) or re.search(r"texto\s+esquerda", text):
        return "left"
    if re.search(r"alinhad[oa]s?\s+centr", text) or re.search(r"texto\s+centr", text):
        return "center"
    return None


def _extract_margins(text: str) -> dict[str, float]:
    margins: dict[str, float] = {}
    side_map = {
        "superior": "margin_top_cm",
        "topo": "margin_top_cm",
        "inferior": "margin_bottom_cm",
        "base": "margin_bottom_cm",
        "esquerda": "margin_left_cm",
        "direita": "margin_right_cm",
    }
    for side, key in side_map.items():
        m = re.search(rf"margem\s+{side}\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*cm", text)
        if m:
            margins[key] = float(m.group(1).replace(",", "."))
    m = re.search(r"margens?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*cm", text)
    if m:
        val = float(m.group(1).replace(",", "."))
        for key in ("margin_top_cm", "margin_bottom_cm", "margin_left_cm", "margin_right_cm"):
            margins.setdefault(key, val)
    return margins


def _extract_header_text(prompt: str) -> str | None:
    m = re.search(
        r"(?:cabe[cç]alho|header)\s*[:\-]?\s*[«\"']?([^«\"'\n.]{3,120})[«\"']?",
        prompt,
        re.I,
    )
    if m:
        return m.group(1).strip(" .\"'")
    return None


def has_format_directives(prompt: str) -> bool:
    lower = prompt.lower()
    return bool(
        _wants_page_numbers(lower)
        or _wants_no_page_numbers(lower)
        or _extract_page_number_position(lower)
        or _extract_font_family(lower)
        or _extract_font_size(lower)
        or _extract_line_spacing(lower)
        or _extract_text_align(lower)
        or _extract_margins(lower)
        or _extract_header_text(prompt)
        or "logo" in lower
    )
