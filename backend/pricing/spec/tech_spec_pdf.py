"""Exportação da Especificação Técnica para PDF — layout técnico (ReportLab)."""

from __future__ import annotations

import html as html_module
import io
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from pricing.spec.tech_spec_layout import (
    HEADING_PT_SIZES,
    document_blocks,
    merge_formatting,
    reportlab_font_bold,
    reportlab_font_name,
)
from pricing.spec.tech_spec_models import TechSpecDocument


def _escape_for_paragraph(text: str) -> str:
    escaped = html_module.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
    return escaped


def _build_styles(fmt: dict[str, Any]) -> dict[str, ParagraphStyle]:
    base_font = reportlab_font_name(str(fmt.get("font_family") or "Arial"))
    bold_font = reportlab_font_bold(str(fmt.get("font_family") or "Arial"))
    body_size = int(fmt.get("font_size") or 11)
    line_leading = body_size * float(fmt.get("line_spacing") or 1.5)

    styles = getSampleStyleSheet()
    result: dict[str, ParagraphStyle] = {}

    align_key = str(fmt.get("text_align") or "justify").lower()
    body_align = TA_JUSTIFY
    if align_key == "left":
        body_align = TA_LEFT
    elif align_key == "center":
        body_align = TA_CENTER

    result["body"] = ParagraphStyle(
        "TechSpecBody",
        parent=styles["Normal"],
        fontName=base_font,
        fontSize=body_size,
        leading=line_leading,
        alignment=body_align,
        spaceBefore=0,
        spaceAfter=4,
    )
    result["title"] = ParagraphStyle(
        "TechSpecTitle",
        parent=result["body"],
        fontName=bold_font,
        fontSize=14,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    result["logo"] = ParagraphStyle(
        "TechSpecLogo",
        parent=result["body"],
        fontSize=body_size,
        alignment=TA_CENTER,
        textColor=colors.grey,
        spaceAfter=8,
    )
    for level in (1, 2, 3, 4):
        size = HEADING_PT_SIZES.get(level, body_size)
        result[f"h{level}"] = ParagraphStyle(
            f"TechSpecH{level}",
            parent=result["body"],
            fontName=bold_font,
            fontSize=size,
            leading=size * 1.15,
            alignment=TA_LEFT,
            spaceBefore=10 if level <= 2 else 6,
            spaceAfter=4,
        )
    result["bullet"] = ParagraphStyle(
        "TechSpecBullet",
        parent=result["body"],
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=2,
    )
    return result


def export_tech_spec_pdf(doc: TechSpecDocument) -> bytes:
    fmt = merge_formatting(doc.formatting)
    styles = _build_styles(fmt)
    display_title = str(fmt.get("document_title") or doc.title or "Especificação Técnica")
    header_text = str(fmt.get("header_text") or display_title).strip()

    buffer = io.BytesIO()
    doc_template = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=float(fmt.get("margin_top_cm") or 3.0) * cm,
        bottomMargin=float(fmt.get("margin_bottom_cm") or 2.0) * cm,
        leftMargin=float(fmt.get("margin_left_cm") or 3.0) * cm,
        rightMargin=float(fmt.get("margin_right_cm") or 2.0) * cm,
        title=display_title,
    )

    story: list[Any] = []

    logo_text = fmt.get("logo_text")
    if logo_text:
        story.append(Paragraph(f"[LOGO: {html_module.escape(str(logo_text))}]", styles["logo"]))

    if display_title:
        story.append(Paragraph(_escape_for_paragraph(display_title), styles["title"]))

    list_items: list[ListItem] = []
    blocks = document_blocks(doc.html_content, doc.markdown)

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            story.append(
                ListFlowable(
                    list_items,
                    bulletType="bullet",
                    start="•",
                    leftIndent=14,
                )
            )
            list_items = []

    for block in blocks:
        btype = block.get("type")
        text = str(block.get("text") or "")
        if not text:
            continue
        if btype == "heading":
            flush_list()
            level = min(max(int(block.get("level") or 1), 1), 4)
            story.append(Paragraph(_escape_for_paragraph(text), styles[f"h{level}"]))
        elif btype == "list_item":
            list_items.append(
                ListItem(Paragraph(_escape_for_paragraph(text), styles["bullet"]), leftIndent=0)
            )
        else:
            flush_list()
            story.append(Paragraph(_escape_for_paragraph(text), styles["body"]))

    flush_list()

    if not story:
        story.append(Paragraph("<i>Documento vazio.</i>", styles["body"]))

    def on_page(canvas: Any, pdf_doc: Any) -> None:
        canvas.saveState()
        font = reportlab_font_name(str(fmt.get("font_family") or "Arial"))
        canvas.setFont(font, 9)
        width, height = A4
        if header_text:
            canvas.drawCentredString(width / 2, height - 1.1 * cm, header_text)
        if fmt.get("page_numbers", True):
            position = str(fmt.get("page_number_position") or "left").lower()
            page_label = f"Página {pdf_doc.page}"
            margin_l = float(fmt.get("margin_left_cm") or 3.0) * cm
            margin_r = float(fmt.get("margin_right_cm") or 2.0) * cm
            if position == "left":
                canvas.drawString(margin_l, 0.9 * cm, page_label)
            elif position == "right":
                canvas.drawRightString(width - margin_r, 0.9 * cm, page_label)
            else:
                canvas.drawCentredString(width / 2, 0.9 * cm, page_label)
        canvas.restoreState()

    doc_template.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buffer.getvalue()
