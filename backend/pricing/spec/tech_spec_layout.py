"""Layout técnico compartilhado (ABNT / documentos de engenharia) para DOCX e PDF."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


def technical_formatting_defaults() -> dict[str, Any]:
    """Padrão para especificação técnica: A4, margens assimétricas, Arial 11, entrelinha 1,5."""
    return {
        "font_family": "Arial",
        "font_size": 11,
        "line_spacing": 1.5,
        "margin_cm": 2.5,
        "margin_top_cm": 3.0,
        "margin_bottom_cm": 2.0,
        "margin_left_cm": 3.0,
        "margin_right_cm": 2.0,
        "header_height_cm": 1.2,
        "footer_height_cm": 1.0,
        "page_numbers": True,
        "page_number_position": "left",
        "text_align": "justify",
        "logo_text": None,
        "document_title": None,
    }


def merge_formatting(fmt: dict[str, Any] | None) -> dict[str, Any]:
    base = technical_formatting_defaults()
    if fmt:
        base.update({k: v for k, v in fmt.items() if v is not None})
    margin = float(base.get("margin_cm") or 2.5)
    base.setdefault("margin_top_cm", margin)
    base.setdefault("margin_bottom_cm", margin)
    base.setdefault("margin_left_cm", margin)
    base.setdefault("margin_right_cm", margin)
    return base


class _HtmlToParagraphs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("h1", "h2", "h3", "h4"):
            self._flush()
            level = int(tag[1])
            self._current = {"type": "heading", "level": level, "runs": []}
        elif tag == "p":
            self._flush()
            self._current = {"type": "paragraph", "runs": []}
        elif tag == "li":
            self._flush()
            self._current = {"type": "list_item", "runs": []}
        elif tag in ("strong", "b"):
            if self._current is not None:
                self._current.setdefault("runs", []).append("**")
        elif tag in ("em", "i"):
            if self._current is not None:
                self._current.setdefault("runs", []).append("*")
        elif tag in ("br",):
            if self._current is not None:
                self._current.setdefault("runs", []).append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("strong", "b"):
            if self._current is not None:
                self._current.setdefault("runs", []).append("**")
        elif tag in ("em", "i"):
            if self._current is not None:
                self._current.setdefault("runs", []).append("*")
        elif tag in ("h1", "h2", "h3", "h4", "p", "li"):
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._current is None:
            self._current = {"type": "paragraph", "runs": []}
        self._current.setdefault("runs", []).append(data)

    def _flush(self) -> None:
        if not self._current:
            return
        text = "".join(self._current.get("runs") or [])
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            self.blocks.append({**self._current, "text": text})
        self._current = None


def parse_html_blocks(html_content: str) -> list[dict[str, Any]]:
    parser = _HtmlToParagraphs()
    parser.feed(html_content or "")
    parser._flush()
    return parser.blocks


def parse_markdown_blocks(markdown_text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for line in markdown_text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            blocks.append(
                {
                    "type": "heading",
                    "level": len(heading.group(1)),
                    "text": heading.group(2).strip(),
                }
            )
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if bullet:
            blocks.append({"type": "list_item", "text": bullet.group(1).strip()})
            continue
        blocks.append({"type": "paragraph", "text": stripped})
    return blocks


def document_blocks(doc_html: str, doc_markdown: str) -> list[dict[str, Any]]:
    if doc_html:
        blocks = parse_html_blocks(doc_html)
        if blocks:
            return blocks
    return parse_markdown_blocks(doc_markdown)


def document_blocks_for_export(doc_html: str, doc_markdown: str) -> list[dict[str, Any]]:
    """Extrai só o corpo editável antes de montar blocos (evita título/logo duplicados)."""
    from pricing.spec.tech_spec_models import extract_body_html

    body_html = extract_body_html(doc_html) if doc_html else ""
    return document_blocks(body_html, doc_markdown)


def docx_font_name(font_family: str) -> str:
    name = (font_family or "Arial").strip()
    if name.lower() in ("arial", "calibri", "verdana", "tahoma"):
        return "Arial"
    if "times" in name.lower():
        return "Times New Roman"
    return name


def reportlab_font_name(font_family: str) -> str:
    name = (font_family or "Arial").strip().lower()
    if "times" in name:
        return "Times-Roman"
    return "Helvetica"


def reportlab_font_bold(font_family: str) -> str:
    name = (font_family or "Arial").strip().lower()
    if "times" in name:
        return "Times-Bold"
    return "Helvetica-Bold"


HEADING_PT_SIZES = {1: 14, 2: 12, 3: 11, 4: 11}
