"""Exportação PDF do laudo — mesmo layout institucional do DOCX."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.inspection_report.analytics import fit_image_display_inches, prepare_watermark_png
from core.inspection_report.format_utils import (
    COLOR_BLUE_HEX,
    COLOR_GRAY_HEX,
    art_traceability_table,
    build_body_sections,
    build_cover_layout,
    build_photographic_index_table,
    build_photographic_presentation,
    build_sumario_entries,
    format_generated_at,
    header_meta_lines,
    inject_coordinates_into_object_tables,
    normalize_parties,
    party_display_lines,
    photo_source_line,
)
from core.system.company_profile import (
    get_company_profile,
    load_company_brasao,
    load_company_logo,
)


def _esc(text: Any) -> str:
    s = str(text or "")
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _make_page_callbacks(
    *,
    org: str,
    company_line: str,
    footer_ref: str,
    logo_bytes: bytes | None,
    meta_lines: list[str],
    watermark_bytes: bytes | None,
):
    from reportlab.lib.utils import ImageReader

    blue = colors.HexColor(COLOR_BLUE_HEX)
    gray = colors.HexColor(COLOR_GRAY_HEX)

    def _draw_header_footer(canvas, doc):
        canvas.saveState()
        page_w, page_h = A4
        left = 2.5 * cm
        right = page_w - 2.0 * cm

        # Marca d'água — largura do corpo da página (margens 2,5 / 2,0 cm)
        if watermark_bytes:
            try:
                canvas.saveState()
                left = 2.5 * cm
                right_m = 2.0 * cm
                body_w = page_w - left - right_m
                reader = ImageReader(io.BytesIO(watermark_bytes))
                iw, ih = reader.getSize()
                if iw > 0 and ih > 0:
                    body_h = body_w * (ih / float(iw))
                    # Limita altura para não estourar a página
                    max_h = page_h - 5.0 * cm
                    if body_h > max_h:
                        scale = max_h / body_h
                        body_h = max_h
                        body_w = body_w * scale
                    x = (page_w - body_w) / 2
                    y = (page_h - body_h) / 2 - 0.3 * cm
                    canvas.drawImage(
                        reader,
                        x,
                        y,
                        width=body_w,
                        height=body_h,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                canvas.restoreState()
            except Exception:
                pass

        # Logo canto superior esquerdo (compacto)
        if logo_bytes:
            try:
                canvas.drawImage(
                    ImageReader(io.BytesIO(logo_bytes)),
                    left,
                    page_h - 1.35 * cm,
                    width=1.35 * cm,
                    height=0.95 * cm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                pass

        canvas.setFont("Times-Bold", 8)
        canvas.setFillColor(blue)
        canvas.drawString(left + 1.55 * cm, page_h - 1.05 * cm, (org or "").upper()[:48])

        canvas.setFillColor(colors.HexColor("#475569"))
        y = page_h - 0.85 * cm
        for i, line in enumerate(meta_lines):
            canvas.setFont("Times-Bold" if i == 0 else "Times-Roman", 7)
            canvas.drawRightString(right, y, (line or "")[:72])
            y -= 0.28 * cm

        y_line = page_h - 1.85 * cm
        canvas.setStrokeColor(blue)
        canvas.setLineWidth(1.3)
        canvas.line(left, y_line, right, y_line)
        canvas.setStrokeColor(gray)
        canvas.setLineWidth(0.6)
        canvas.line(left, y_line - 0.10 * cm, right, y_line - 0.10 * cm)

        y_foot = 1.85 * cm
        canvas.setStrokeColor(blue)
        canvas.setLineWidth(1.3)
        canvas.line(left, y_foot, right, y_foot)
        canvas.setStrokeColor(gray)
        canvas.setLineWidth(0.6)
        canvas.line(left, y_foot - 0.10 * cm, right, y_foot - 0.10 * cm)

        canvas.setFont("Times-Roman", 7)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawCentredString(page_w / 2, 1.4 * cm, (company_line or "")[:120])
        canvas.setFont("Times-Roman", 8)
        canvas.drawCentredString(
            page_w / 2,
            1.05 * cm,
            f"Página {doc.page}  |  {(footer_ref or '')[:70]}",
        )
        canvas.restoreState()

    return _draw_header_footer


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "LaudoTitle",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=5,
            leading=18,
        ),
        "subtitle": ParagraphStyle(
            "LaudoSubtitle",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=8,
            leading=13,
        ),
        "h1": ParagraphStyle(
            "LaudoH1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=12,
            textColor=colors.HexColor(COLOR_BLUE_HEX),
            spaceBefore=12,
            spaceAfter=7,
            leading=15,
        ),
        "h2": ParagraphStyle(
            "LaudoH2",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=11,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=8,
            spaceAfter=5,
            leading=13,
        ),
        "h2_center": ParagraphStyle(
            "LaudoH2Center",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=11,
            textColor=colors.HexColor("#0F172A"),
            alignment=TA_CENTER,
            spaceBefore=8,
            spaceAfter=5,
            leading=13,
        ),
        "sig_name": ParagraphStyle(
            "LaudoSigName",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=10,
            alignment=TA_CENTER,
            leading=12,
            spaceAfter=1,
        ),
        "sig_line": ParagraphStyle(
            "LaudoSigLine",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            alignment=TA_CENTER,
            leading=12,
            spaceAfter=1,
        ),
        "body": ParagraphStyle(
            "LaudoBody",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=15,
            alignment=TA_JUSTIFY,
            firstLineIndent=1.5 * cm,
            spaceAfter=7,
        ),
        "meta": ParagraphStyle(
            "LaudoMeta",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            firstLineIndent=0,
            spaceAfter=2,
        ),
        "cover_section": ParagraphStyle(
            "LaudoCoverSection",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=10,
            textColor=colors.HexColor(COLOR_BLUE_HEX),
            alignment=TA_LEFT,
            firstLineIndent=0,
            spaceBefore=10,
            spaceAfter=4,
            leading=12,
        ),
        "cover_label": ParagraphStyle(
            "LaudoCoverLabel",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            firstLineIndent=0,
        ),
        "cover_value": ParagraphStyle(
            "LaudoCoverValue",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
            firstLineIndent=0,
        ),
        "cover_note": ParagraphStyle(
            "LaudoCoverNote",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=9,
            leading=12,
            alignment=TA_JUSTIFY,
            firstLineIndent=0,
            spaceAfter=6,
        ),
        "caption": ParagraphStyle(
            "LaudoCaption",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            spaceBefore=4,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "LaudoCell",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=7.5,
            leading=9.5,
            alignment=TA_LEFT,
        ),
        "cell_h": ParagraphStyle(
            "LaudoCellH",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=7.5,
            leading=9.5,
            alignment=TA_LEFT,
        ),
        "card_label": ParagraphStyle(
            "CardLabel",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#64748B"),
            leading=10,
        ),
        "card_value": ParagraphStyle(
            "CardValue",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor(COLOR_BLUE_HEX),
            leading=13,
        ),
        "card_hint": ParagraphStyle(
            "CardHint",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=7,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#94A3B8"),
            leading=9,
        ),
        "legend": ParagraphStyle(
            "LaudoLegend",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_JUSTIFY,
            spaceAfter=3,
        ),
        "meta_left": ParagraphStyle(
            "LaudoMetaLeft",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
            firstLineIndent=0,
            spaceAfter=3,
        ),
    }


def _table_style():
    return TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94A3B8")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
    )


def _make_flow_table(headers: list, rows: list, styles: dict, col_widths: list[float] | None = None):
    cell = styles["cell"]
    cell_h = styles["cell_h"]
    data = [[Paragraph(_esc(h), cell_h) for h in headers]]
    for row in rows:
        data.append(
            [Paragraph(_esc(row[i] if i < len(row) else ""), cell) for i in range(len(headers))]
        )
    t = Table(data, hAlign="LEFT", colWidths=col_widths, repeatRows=1)
    t.setStyle(_table_style())
    return t


def _make_cards(cards: list[dict[str, Any]], styles: dict) -> list[Any]:
    if not cards:
        return []
    flow: list[Any] = []
    chunk = 3
    usable = 16.5 * cm
    for i in range(0, len(cards), chunk):
        group = cards[i : i + chunk]
        cols = []
        for card in group:
            inner = [
                Paragraph(_esc(card.get("label") or ""), styles["card_label"]),
                Spacer(1, 3),
                Paragraph(_esc(card.get("value") or ""), styles["card_value"]),
            ]
            if card.get("hint"):
                inner.append(Spacer(1, 2))
                inner.append(Paragraph(_esc(card["hint"]), styles["card_hint"]))
            cols.append(inner)
        col_w = usable / len(group)
        data = [cols]
        t = Table(data, colWidths=[col_w] * len(group), hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        flow.append(t)
        flow.append(Spacer(1, 8))
    return flow


def _make_kv_table(rows: list[list[str]], styles: dict) -> Table:
    data = []
    for row in rows:
        label = str(row[0] if row else "")
        value = str(row[1] if len(row) > 1 else "")
        data.append(
            [
                Paragraph(_esc(label), styles["cover_label"]),
                Paragraph(_esc(value), styles["cover_value"]),
            ]
        )
    t = Table(data, colWidths=[4.8 * cm, 11.7 * cm], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94A3B8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8EEF9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _cover_flow(content: dict[str, Any], styles: dict, *, generated_at: str) -> list[Any]:
    cover = build_cover_layout(content, generated_at=generated_at)
    flow: list[Any] = [
        Paragraph(_esc(str(cover["titulo"]).upper()), styles["title"]),
    ]
    if cover.get("subtitulo"):
        flow.append(Paragraph(_esc(cover["subtitulo"]), styles["subtitle"]))

    # Régua azul sob o título
    rule = Table([[""]], colWidths=[16.5 * cm], rowHeights=[1.2])
    rule.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(COLOR_BLUE_HEX)),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    flow.append(Spacer(1, 4))
    flow.append(rule)
    flow.append(Spacer(1, 8))

    for block in cover.get("blocks") or []:
        heading = str(block.get("heading") or "").strip()
        rows = block.get("rows") or []
        if not rows:
            continue
        if heading:
            flow.append(Paragraph(_esc(heading.upper()), styles["cover_section"]))
        flow.append(_make_kv_table(rows, styles))
        flow.append(Spacer(1, 6))

    flow.append(
        Paragraph(
            _esc(f"Documento gerado em: {generated_at}"),
            styles["cover_note"],
        )
    )
    note = cover.get("compliance_note") or ""
    if note:
        flow.append(Paragraph(_esc("CONFORMIDADE NORMATIVA"), styles["cover_section"]))
        flow.append(Paragraph(_esc(note), styles["cover_note"]))
    flow.append(Spacer(1, 6))
    return flow


def _signatures_flow(
    content: dict[str, Any],
    styles: dict,
    signature_paths: dict[str, str] | None = None,
) -> list[Any]:
    parties = normalize_parties(content.get("responsaveis_tecnicos"))
    if not parties:
        return []
    sig_map = signature_paths or {}
    flow: list[Any] = [
        PageBreak(),
        Paragraph(_esc("Responsáveis técnicos"), styles["h1"]),
        Paragraph(
            _esc(
                "Declaramos, para os devidos fins, a responsabilidade técnica pelo presente laudo, "
                "nos termos das normas aplicáveis e do registro profissional abaixo indicado."
            ),
            styles["body"],
        ),
        Spacer(1, 24),
    ]

    def _party_block(party: dict[str, Any]) -> list[Any]:
        inner: list[Any] = []
        path = sig_map.get(str(party.get("id") or ""))
        if path and Path(path).exists():
            try:
                img = Image(path, width=4.5 * cm, height=1.8 * cm, kind="proportional")
                img.hAlign = "CENTER"
                inner.append(img)
                inner.append(Spacer(1, 4))
            except Exception:
                inner.append(Paragraph(_esc("_______________________________"), styles["sig_line"]))
                inner.append(Spacer(1, 4))
        else:
            inner.append(Paragraph(_esc("_______________________________"), styles["sig_line"]))
            inner.append(Spacer(1, 4))
        for idx, line in enumerate(party_display_lines(party)):
            style = styles["sig_name"] if idx == 0 else styles["sig_line"]
            inner.append(Paragraph(_esc(line), style))
        return inner

    if len(parties) == 1:
        flow.extend(_party_block(parties[0]))
        flow.append(Spacer(1, 16))
        return flow

    for i in range(0, len(parties), 2):
        chunk = parties[i : i + 2]
        cells = [_party_block(party) for party in chunk]
        widths = [8.0 * cm, 8.0 * cm] if len(chunk) == 2 else [16.5 * cm]
        t = Table([cells], colWidths=widths[: len(chunk)], hAlign="CENTER")
        t.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        flow.append(t)
        flow.append(Spacer(1, 16))
    return flow


def build_inspection_laudo_pdf(
    *,
    content: dict[str, Any],
    image_assets: list[dict[str, Any]],
    georef_asset: dict[str, Any] | None = None,
    signature_paths: dict[str, str] | None = None,
) -> bytes:
    generated_at = format_generated_at(datetime.now())
    company = get_company_profile()
    company_source = company.display_name() or "Empresa responsável"
    org = company_source
    company_line = " | ".join(
        x for x in (company.endereco_linha(), company.site or company.email) if x
    ) or org

    export_content = dict(content or {})
    if georef_asset and georef_asset.get("latitude") is not None:
        export_content = inject_coordinates_into_object_tables(
            export_content,
            latitude=georef_asset.get("latitude"),
            longitude=georef_asset.get("longitude"),
            label=georef_asset.get("label"),
        )

    footer_ref = str(export_content.get("numero_laudo") or export_content.get("titulo") or "Laudo técnico")
    meta_lines = header_meta_lines(export_content, generated_at=generated_at)

    logo_bytes = load_company_logo()
    brasao_raw = load_company_brasao()
    watermark_bytes = None
    if brasao_raw:
        # PNG com alpha; canvas desenha na largura do corpo
        watermark_bytes = prepare_watermark_png(
            brasao_raw, size_px=1800, opacity=0.06, max_width_px=1800
        ) or brasao_raw

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.3 * cm,
    )
    styles = _styles()
    story: list[Any] = []

    story.extend(_cover_flow(export_content, styles, generated_at=generated_at))

    sumario_entries = build_sumario_entries(export_content)
    if sumario_entries:
        story.append(PageBreak())
        story.append(Paragraph(_esc("Sumário"), styles["h1"]))
        story.append(
            Paragraph(
                _esc("O presente laudo está estruturado conforme as seções abaixo."),
                styles["meta"],
            )
        )
        story.append(Spacer(1, 8))
        for idx, entry in enumerate(sumario_entries, start=1):
            label = (entry.get("label") or "").strip()
            if not label:
                continue
            # Labels já vêm numerados de build_body_sections / build_sumario_entries
            story.append(Paragraph(_esc(label), styles["body"]))
        story.append(Spacer(1, 10))

    sections = build_body_sections(export_content)
    usable = 16.5 * cm

    for section in sections:
        story.append(Paragraph(_esc(section["title"]), styles["h1"]))
        if section.get("cards"):
            story.extend(_make_cards(section["cards"], styles))
        for para in section.get("paragraphs") or []:
            story.append(Paragraph(_esc(para), styles["body"]))
        for table in section.get("tables") or []:
            headers = table.get("headers") or []
            rows = table.get("rows") or []
            if not headers:
                continue
            if table.get("caption"):
                story.append(Paragraph(_esc(table["caption"]), styles["caption"]))
            ncols = len(headers)
            if ncols == 8:
                # ID um pouco mais largo — evita quebra feia em element_id
                widths = [1.8 * cm, 1.4 * cm, 2.8 * cm, 2.0 * cm, 1.5 * cm, 1.3 * cm, 1.5 * cm, 2.2 * cm]
            elif ncols == 7:
                widths = [1.3 * cm, 2.8 * cm, 2.3 * cm, 1.7 * cm, 1.2 * cm, 4.0 * cm, 2.2 * cm]
            elif ncols == 4:
                widths = [2.5 * cm, 2.5 * cm, 2.5 * cm, 9.0 * cm]
            elif ncols == 2:
                widths = [5.5 * cm, 11.0 * cm]
            else:
                widths = [usable / ncols] * ncols
            story.append(_make_flow_table(headers, rows, styles, widths))
            story.append(Spacer(1, 6))

        cid = str(section.get("chapter_id") or "")
        title_l = str(section.get("title") or "").lower()
        is_ficha = cid == "ficha_tecnica" or "ficha técnica" in title_l or "ficha tecnica" in title_l
        if is_ficha and georef_asset:
            has_gps = (
                georef_asset.get("latitude") is not None
                and georef_asset.get("longitude") is not None
            )
            geo_path = georef_asset.get("path")
            if has_gps and geo_path and Path(geo_path).exists():
                try:
                    from core.inspection_report.location_map import (
                        FRAME_HEIGHT_IN,
                        FRAME_WIDTH_IN,
                        frame_image_for_export,
                        georef_photo_caption,
                    )

                    framed = frame_image_for_export(str(geo_path))
                    img = Image(
                        io.BytesIO(framed),
                        width=FRAME_WIDTH_IN * inch,
                        height=FRAME_HEIGHT_IN * inch,
                    )
                    img.hAlign = "CENTER"
                    story.append(img)
                    story.append(Paragraph(_esc(georef_photo_caption(georef_asset)), styles["meta"]))
                    story.append(Spacer(1, 6))
                except Exception:
                    story.append(
                        Paragraph(_esc("[Falha ao inserir imagem georreferenciada]"), styles["meta"])
                    )
            if has_gps:
                try:
                    from core.inspection_report.location_map import (
                        FRAME_HEIGHT_IN,
                        FRAME_WIDTH_IN,
                        build_location_map_png,
                        frame_image_for_export,
                        location_map_caption,
                        location_map_source,
                    )

                    map_png = build_location_map_png(
                        float(georef_asset["latitude"]),
                        float(georef_asset["longitude"]),
                        cache_path=georef_asset.get("map_cache_path"),
                    )
                    if map_png:
                        framed_map = frame_image_for_export(map_png)
                        map_img = Image(
                            io.BytesIO(framed_map),
                            width=FRAME_WIDTH_IN * inch,
                            height=FRAME_HEIGHT_IN * inch,
                        )
                        map_img.hAlign = "CENTER"
                        story.append(map_img)
                        story.append(
                            Paragraph(
                                _esc(
                                    location_map_caption(
                                        float(georef_asset["latitude"]),
                                        float(georef_asset["longitude"]),
                                        georef_asset.get("label"),
                                        source=location_map_source(
                                            georef_asset.get("map_cache_path")
                                        ),
                                    )
                                ),
                                styles["meta"],
                            )
                        )
                        story.append(Spacer(1, 8))
                except Exception:
                    pass

        for ch_img in section.get("chart_images") or []:
            if ch_img.get("caption"):
                story.append(Paragraph(_esc(ch_img["caption"]), styles["caption"]))
            png = ch_img.get("png")
            if png:
                try:
                    img = Image(io.BytesIO(png), width=15.5 * cm, height=7.2 * cm, kind="proportional")
                    img.hAlign = "CENTER"
                    story.append(img)
                    story.append(Spacer(1, 8))
                except Exception:
                    pass

    story.extend(_signatures_flow(export_content, styles, signature_paths))

    art_tbl = art_traceability_table(export_content)
    if art_tbl:
        story.append(Paragraph(_esc("ART e documentos técnicos"), styles["h2"]))
        story.append(
            Paragraph(
                _esc("Rastreabilidade de ART/anexos dos responsáveis técnicos (L18)."),
                styles["body"],
            )
        )
        headers = art_tbl.get("headers") or []
        rows = art_tbl.get("rows") or []
        data = [headers] + rows
        t = Table(data, colWidths=[3.2 * cm, 2.2 * cm, 2.2 * cm, 2.5 * cm, 1.8 * cm, 4.6 * cm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF9")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 10))

    next_num = (sections[-1]["number"] + 1) if sections else 1
    index_table = build_photographic_index_table(export_content)
    if index_table:
        story.append(PageBreak())
        story.append(
            Paragraph(_esc(f"{next_num}. Índice do relatório fotográfico"), styles["h1"])
        )
        story.append(
            Paragraph(
                _esc(
                    "Relação ordenada das fotografias com vínculo a elemento e patologias, "
                    "para localização rápida no anexo."
                ),
                styles["body"],
            )
        )
        headers = index_table.get("headers") or []
        rows = index_table.get("rows") or []
        if headers:
            if index_table.get("caption"):
                story.append(Paragraph(_esc(index_table["caption"]), styles["caption"]))
            widths = [1.5 * cm, 6.0 * cm, 3.0 * cm, 2.5 * cm, 3.5 * cm]
            story.append(_make_flow_table(headers, rows, styles, widths))
            story.append(Spacer(1, 6))
        next_num += 1

    story.append(PageBreak())
    story.append(Paragraph(_esc(f"{next_num}. Relatório fotográfico"), styles["h1"]))
    story.append(Paragraph(_esc(build_photographic_presentation(export_content)), styles["body"]))

    photo_entries = export_content.get("photographic_report") or []
    path_by_file = {a["filename"].lower(): a for a in image_assets}
    path_by_num = {int(a["photo_number"]): a for a in image_assets if a.get("photo_number")}
    ordered = sorted(photo_entries, key=lambda p: int(p.get("photo_number") or 0))
    if not ordered:
        ordered = [
            {
                "photo_number": a.get("photo_number"),
                "filename": a["filename"],
                "title": f"Foto {a.get('photo_number') or '':02d}",
                "description": a.get("caption") or "Registro fotográfico.",
                "legend": "",
            }
            for a in image_assets
        ]

    for entry in ordered:
        story.append(PageBreak())
        num = int(entry.get("photo_number") or 0)
        block: list[Any] = [
            Paragraph(
                _esc(f"Foto {num:02d} – {entry.get('title') or entry.get('filename') or ''}"),
                styles["h2_center"],
            )
        ]
        asset = path_by_num.get(num) or path_by_file.get(str(entry.get("filename") or "").lower())
        if asset and Path(asset["path"]).exists():
            try:
                from core.inspection_report.visual_memory import image_bytes_with_visual_memory

                dw, dh = fit_image_display_inches(str(asset["path"]), max_w=5.9, max_h=5.0)
                img_bytes = image_bytes_with_visual_memory(
                    str(asset["path"]),
                    export_content,
                    asset_id=asset.get("asset_id"),
                    photo_number=num or asset.get("photo_number"),
                )
                img = Image(
                    io.BytesIO(img_bytes),
                    width=dw * inch,
                    height=dh * inch,
                    kind="proportional",
                )
                img.hAlign = "CENTER"
                block.append(img)
                block.append(Spacer(1, 4))
            except Exception:
                block.append(
                    Paragraph(_esc(f"[Falha ao inserir {asset['filename']}]"), styles["meta_left"])
                )
        block.append(
            Paragraph(f"<b>Descrição:</b> {_esc(entry.get('description') or '—')}", styles["body"])
        )
        if entry.get("legend"):
            block.append(Paragraph(f"Legenda: {_esc(entry.get('legend'))}", styles["legend"]))
        block.append(Paragraph(_esc(photo_source_line(export_content)), styles["meta"]))
        story.append(KeepTogether(block))

    on_page = _make_page_callbacks(
        org=org,
        company_line=company_line,
        footer_ref=footer_ref,
        logo_bytes=logo_bytes,
        meta_lines=meta_lines,
        watermark_bytes=watermark_bytes or brasao_raw,
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
