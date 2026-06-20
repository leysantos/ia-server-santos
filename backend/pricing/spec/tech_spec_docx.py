"""Exportação da Especificação Técnica para DOCX (Word)."""

from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from typing import Any

from pricing.spec.tech_spec_models import TechSpecDocument, default_formatting, render_document_html


class _HtmlToParagraphs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self._list_level = 0

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
                self._current.setdefault("bold", True)
        elif tag in ("em", "i"):
            if self._current is not None:
                self._current.setdefault("italic", True)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h1", "h2", "h3", "h4", "p", "li"):
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._current is None:
            self._current = {"type": "paragraph", "runs": []}
        self._current.setdefault("runs", []).append(data)

    def _flush(self) -> None:
        if not self._current:
            return
        text = "".join(self._current.get("runs") or []).strip()
        if text or self._current.get("type") == "paragraph":
            self.blocks.append({**self._current, "text": text})
        self._current = None


def _parse_html_blocks(html_content: str) -> list[dict[str, Any]]:
    parser = _HtmlToParagraphs()
    parser.feed(html_content or "<p></p>")
    parser._flush()
    return parser.blocks


def _parse_markdown_blocks(markdown_text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for line in markdown_text.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            blocks.append({"type": "paragraph", "text": ""})
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
        blocks.append({"type": "paragraph", "text": line.strip()})
    return blocks


def export_tech_spec_docx(doc: TechSpecDocument) -> bytes:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm, Pt
    except ImportError as exc:
        raise ImportError("python-docx necessário: pip install python-docx") from exc

    fmt = doc.formatting or default_formatting()
    font_name = str(fmt.get("font_family") or "Calibri")
    font_size = int(fmt.get("font_size") or 11)
    margin = float(fmt.get("margin_cm") or 2.5)

    document = Document()
    for section in document.sections:
        section.top_margin = Cm(margin)
        section.bottom_margin = Cm(margin)
        section.left_margin = Cm(margin)
        section.right_margin = Cm(margin)
        if fmt.get("page_numbers"):
            _add_page_number_footer(section)

    style = document.styles["Normal"]
    style.font.name = font_name
    style.font.size = Pt(font_size)

    display_title = fmt.get("document_title") or doc.title
    logo_text = fmt.get("logo_text")
    if logo_text:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"[LOGO: {logo_text}]")
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.italic = True

    if display_title:
        title_p = document.add_heading(str(display_title), level=0)
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    blocks = (
        _parse_html_blocks(doc.html_content)
        if doc.html_content
        else _parse_markdown_blocks(doc.markdown)
    )

    for block in blocks:
        btype = block.get("type")
        text = str(block.get("text") or "")
        if btype == "heading":
            level = min(int(block.get("level") or 1), 4)
            document.add_heading(text, level=level)
        elif btype == "list_item":
            document.add_paragraph(text, style="List Bullet")
        else:
            p = document.add_paragraph()
            _add_runs_from_text(p, text, font_name, font_size)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _add_runs_from_text(paragraph: Any, text: str, font_name: str, font_size: int) -> None:
    from docx.shared import Pt

    pattern = re.compile(r"(\*\*.+?\*\*|\*.+?\*)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos : match.start()])
            run.font.name = font_name
            run.font.size = Pt(font_size)
        chunk = match.group(0)
        if chunk.startswith("**"):
            run = paragraph.add_run(chunk[2:-2])
            run.bold = True
        else:
            run = paragraph.add_run(chunk[1:-1])
            run.italic = True
        run.font.name = font_name
        run.font.size = Pt(font_size)
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        run.font.name = font_name
        run.font.size = Pt(font_size)


def _add_page_number_footer(section: Any) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    footer = section.footer
    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("Página ")

    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_begin)

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    run._r.append(instr)

    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    run._r.append(fld_sep)

    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_end)
