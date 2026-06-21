"""Geração de GRD — Guia de Remessa de Documentos."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def generate_grd_pdf(
    *,
    project_name: str,
    project_codigo: str | None,
    cliente: str | None,
    codigo_emissao: str,
    responsavel: str | None,
    items: list[dict[str, Any]],
) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "GUIA DE REMESSA DE DOCUMENTOS (GRD)")
    y -= 8 * mm

    c.setFont("Helvetica", 10)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    for line in (
        f"Projeto: {project_name}",
        f"Código: {project_codigo or '—'}",
        f"Cliente: {cliente or '—'}",
        f"Emissão: {codigo_emissao}",
        f"Responsável: {responsavel or '—'}",
        f"Data: {now}",
        f"Total de documentos: {len(items)}",
    ):
        c.drawString(margin, y, line)
        y -= 5 * mm

    y -= 4 * mm
    c.setFont("Helvetica-Bold", 9)
    headers = ("Item", "Código", "Arquivo", "Disciplina", "Pasta")
    col_x = [margin, margin + 12 * mm, margin + 45 * mm, margin + 110 * mm, margin + 145 * mm]
    for i, h in enumerate(headers):
        c.drawString(col_x[i], y, h)
    y -= 3 * mm
    c.setStrokeColor(colors.grey)
    c.line(margin, y, width - margin, y)
    y -= 5 * mm

    c.setFont("Helvetica", 8)
    for idx, item in enumerate(items, start=1):
        if y < margin + 20 * mm:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 8)

        codigo = item.get("codigo_aprovado") or item.get("codigo_sugerido") or "—"
        arquivo = item.get("arquivo_final") or item.get("filename") or "—"
        disciplina = item.get("disciplina_codigo") or item.get("disciplina") or "—"
        pasta = item.get("pasta_destino") or "—"

        c.drawString(col_x[0], y, str(idx))
        c.drawString(col_x[1], y, str(codigo)[:28])
        c.drawString(col_x[2], y, str(arquivo)[:38])
        c.drawString(col_x[3], y, str(disciplina)[:12])
        c.drawString(col_x[4], y, str(pasta)[:28])
        y -= 4.5 * mm

    c.showPage()
    c.save()
    return buffer.getvalue()
