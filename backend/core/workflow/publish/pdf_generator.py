"""Geração de PDF de pranchas — ReportLab."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A1, A2, A3, A4, A0, landscape, portrait
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from core.workflow.template_engine.engine import build_sheet_context, render_default_sheet
from core.workflow.publish.stamp_audit import build_stamp_audit, format_stamp_audit_lines

_FORMATS = {
    "A4": A4,
    "A3": A3,
    "A2": A2,
    "A1": A1,
    "A0": A0,
}


def _page_size(formato: str, orientacao: str) -> tuple[float, float]:
    base = _FORMATS.get(formato.upper(), A1)
    return landscape(base) if orientacao.lower().startswith("pais") else portrait(base)


def generate_sheet_pdf(context: dict[str, Any]) -> bytes:
    """Gera PDF de prancha com carimbo, legenda e metadados."""
    formato = str(context.get("formato", "A1"))
    orientacao = str(context.get("orientacao", "paisagem"))
    page_size = _page_size(formato, orientacao)
    width, height = page_size

    sheet_ctx = build_sheet_context(
        empresa=str(context.get("empresa", "")),
        autor=str(context.get("autor", context.get("responsavel", ""))),
        crea=str(context.get("crea", "")),
        escala=str(context.get("escala", "1:100")),
        titulo=str(context.get("titulo", context.get("filename", "Desenho"))),
        codigo=str(context.get("codigo", "")),
        revisao=str(context.get("revisao", "REV00")),
    )
    preview = render_default_sheet(sheet_ctx)

    audit = context.get("stamp_audit")
    if not audit and context.get("analysis_json"):
        audit = build_stamp_audit(analysis_json=context.get("analysis_json"))
    audit_lines = format_stamp_audit_lines(audit) if audit else []

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=page_size)

    # Área de desenho
    margin = 15 * mm
    stamp_h = 38 * mm if audit_lines else 30 * mm
    draw_x = margin
    draw_y = margin + stamp_h
    draw_w = width - 2 * margin
    draw_h = height - draw_y - margin
    c.setStrokeColor(colors.lightgrey)
    c.setFillColor(colors.whitesmoke)
    c.rect(draw_x, draw_y, draw_w, draw_h, fill=1, stroke=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(draw_x + 8, draw_y + draw_h - 16, f"Área técnica — {sheet_ctx['titulo']}")
    c.drawString(draw_x + 8, draw_y + draw_h - 30, f"Classificação: {context.get('classificacao', 'desenho_tecnico')}")
    c.drawString(draw_x + 8, draw_y + draw_h - 44, f"Escala: {sheet_ctx['escala']}")

    # Carimbo inferior
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.rect(margin, margin, width - 2 * margin, stamp_h, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 6, margin + stamp_h - 12, sheet_ctx["empresa"] or "IA Server Santos")
    c.setFont("Helvetica", 8)
    lines = preview.splitlines()
    y = margin + stamp_h - 24
    for line in lines[:3]:
        c.drawString(margin + 6, y, line[:90])
        y -= 10

    # Bloco auditoria IA / NBRs (centro-direita do carimbo)
    if audit_lines:
        audit_x = width * 0.42
        audit_y = margin + stamp_h - 14
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(colors.HexColor("#333333"))
        c.drawString(audit_x, audit_y, "RASTREABILIDADE IA")
        c.setFont("Helvetica", 5.5)
        audit_y -= 8
        for line in audit_lines[:6]:
            c.drawString(audit_x, audit_y, line[:95])
            audit_y -= 7

    # QR placeholder
    qr_size = 22 * mm
    c.setFillColor(colors.black)
    c.rect(width - margin - qr_size - 4, margin + 4, qr_size, qr_size, stroke=1, fill=0)
    c.setFont("Helvetica", 6)
    c.drawString(width - margin - qr_size, margin + 2, "QR")

    c.showPage()
    c.save()
    return buffer.getvalue()


def generate_publication_pdf(context: dict[str, Any], sheets: list[dict[str, Any]] | None = None) -> bytes:
    """PDF consolidado de publicação (capa + índice de pranchas)."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=portrait(A4))
    width, height = portrait(A4)

    title = str(context.get("titulo", context.get("project_name", "Publicação de Projeto")))
    revisao = str(context.get("revisao", "REV00"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 60, title)
    c.setFont("Helvetica", 11)
    c.drawString(40, height - 85, f"Revisão: {revisao}")
    c.drawString(40, height - 102, f"Cliente: {context.get('cliente', '—')}")
    c.drawString(40, height - 119, f"Responsável: {context.get('responsavel', '—')}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, height - 155, "Índice de pranchas")
    c.setFont("Helvetica", 10)
    y = height - 175
    for idx, sheet in enumerate(sheets or [], start=1):
        label = sheet.get("numero_prancha") or f"{idx:02d}"
        codigo = sheet.get("codigo_desenho") or sheet.get("codigo") or "—"
        escala = sheet.get("escala") or "—"
        c.drawString(50, y, f"Prancha {label} — {codigo} — escala {escala}")
        y -= 14
        if y < 60:
            c.showPage()
            y = height - 60

    c.showPage()
    c.save()
    return buffer.getvalue()
