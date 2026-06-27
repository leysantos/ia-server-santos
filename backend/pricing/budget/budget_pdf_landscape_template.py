"""Template PDF paisagem para documentos de orçamento (modelo orç. sintético).

Aplicável a: orc_sintetico, orc_analitico, cronograma.
"""

from __future__ import annotations

import html
import io
import os
import tempfile
from dataclasses import dataclass
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.system.company_profile import CompanyProfile
from pricing.budget.budget_export_branding import ExportBrandingConfig
from pricing.models.budget_metadata import BudgetProjectMetadata

TEMPLATE_ID = "landscape_budget_v1"

LANDSCAPE_BUDGET_DOC_TYPES = frozenset(
    {"orc_sintetico", "orc_analitico", "cronograma", "curva_abc", "curva_s", "histograma"}
)

HEADER_BLUE = colors.HexColor("#1F4E79")
STRIPE_GRAY = colors.HexColor("#F2F2F2")
MARGIN_LR = 1.2 * cm
MARGIN_BOTTOM = 1.7 * cm
HEADER_PAD_TOP = 0.40 * cm
HEADER_CONTENT_PAD_TOP = 0.26 * cm
HEADER_LOGO_H = 0.9 * cm
HEADER_LOGO_W = 2.2 * cm
HEADER_GAP_AFTER_TEXT = 0.42 * cm
META_PAD_AFTER_SEP = 0.10 * cm
META_ROW_HEIGHT = 0.30 * cm
META_GAP_BEFORE_CONTENT = 0.08 * cm
HEADER_TITLE_LEAD = 0.34 * cm
HEADER_LINE_LEAD = 0.30 * cm
HEADER_FONT_DESCENT = 0.08 * cm
FRAME_LINE_WIDTH = 0.6

LANDSCAPE_PAGESIZE = landscape(A4)


@dataclass(frozen=True)
class LandscapePdfContext:
    title: str
    brand: ExportBrandingConfig
    profile: CompanyProfile
    header_lines: list[str]
    logo_path: str | None
    brasao_path: str | None
    has_side_images: bool
    meta: BudgetProjectMetadata | None = None
    show_obra_meta: bool = False


def meta_block_height() -> float:
    return META_PAD_AFTER_SEP + 2 * META_ROW_HEIGHT + META_GAP_BEFORE_CONTENT


def folha_page_label(page_num: int, total_pages: int) -> str:
    return f"Pagina {page_num:02d}/{total_pages:02d}"


class FolhaNumberedCanvas(rl_canvas.Canvas):
    """Canvas em duas passagens para exibir total de folhas (Pagina 01/03 folhas)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_folha_label(total)
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)

    def _draw_folha_label(self, total_pages: int) -> None:
        page_w, _ = self._pagesize
        self.saveState()
        self.setFont("Helvetica", 6.5)
        label = folha_page_label(self._pageNumber, total_pages)
        self.drawRightString(page_w - MARGIN_LR, 0.55 * cm, label)
        self.restoreState()


def write_temp_image(image_bytes: bytes | None) -> str | None:
    if not image_bytes:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            return tmp.name
    except OSError:
        return None


def cleanup_temp_images(paths: list[str | None]) -> None:
    for path in paths:
        if not path:
            continue
        try:
            os.unlink(path)
        except OSError:
            pass


def header_top_margin(has_side_images: bool, subtitle_line_count: int) -> float:
    text_h = HEADER_TITLE_LEAD + subtitle_line_count * HEADER_LINE_LEAD + HEADER_FONT_DESCENT
    inner = text_h + HEADER_CONTENT_PAD_TOP + 0.06 * cm
    if has_side_images:
        content_h = max(HEADER_LOGO_H, inner)
    else:
        content_h = inner
    band = HEADER_PAD_TOP + content_h
    return band + HEADER_GAP_AFTER_TEXT


def build_landscape_context(
    *,
    title: str,
    brand: ExportBrandingConfig,
    profile: CompanyProfile,
    logo_path: str | None,
    brasao_path: str | None,
    meta: BudgetProjectMetadata | None = None,
    show_obra_meta: bool = False,
) -> LandscapePdfContext:
    header_lines = [
        brand.header_line1 or profile.display_name(),
        brand.header_line2,
        brand.header_line3,
    ]
    active = [ln for ln in header_lines if ln]
    return LandscapePdfContext(
        title=title,
        brand=brand,
        profile=profile,
        header_lines=active,
        logo_path=logo_path,
        brasao_path=brasao_path,
        has_side_images=bool(logo_path),
        meta=meta,
        show_obra_meta=show_obra_meta,
    )


def render_landscape_pdf(
    story: list[Any],
    *,
    ctx: LandscapePdfContext,
) -> bytes:
    buffer = io.BytesIO()
    top_margin = header_top_margin(ctx.has_side_images, len(ctx.header_lines))
    if ctx.show_obra_meta and ctx.meta:
        top_margin += meta_block_height()

    def on_page(canvas, doc_template):
        draw_page_frame(canvas, doc_template, ctx)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=LANDSCAPE_PAGESIZE,
        topMargin=top_margin,
        bottomMargin=MARGIN_BOTTOM,
        leftMargin=MARGIN_LR,
        rightMargin=MARGIN_LR,
        title=ctx.title,
    )
    doc.build(
        story,
        onFirstPage=on_page,
        onLaterPages=on_page,
        canvasmaker=FolhaNumberedCanvas,
    )
    return buffer.getvalue()


def _draw_meta_cell(
    canvas,
    text: str,
    x: float,
    y_bottom: float,
    width: float,
    style: ParagraphStyle,
) -> None:
    if not text:
        return
    paragraph = Paragraph(html.escape(str(text)), style)
    paragraph.wrap(width, META_ROW_HEIGHT)
    paragraph.drawOn(canvas, x, y_bottom)


def draw_obra_meta_on_canvas(canvas, doc, meta: BudgetProjectMetadata) -> None:
    """Desenha bloco 2×2 obra/bases entre o cabeçalho institucional e o conteúdo."""
    styles = cell_styles()
    page_w, page_h = doc.pagesize
    left = doc.leftMargin
    col_w = (page_w - left - doc.rightMargin) / 2 - 4

    obra_l1, obra_l2 = format_obra_meta_obra_lines(meta)
    price_l1, price_l2 = format_obra_meta_pricing_lines(meta)

    content_top = page_h - doc.topMargin
    meta_bottom = content_top - META_GAP_BEFORE_CONTENT
    y_row2 = meta_bottom
    y_row1 = meta_bottom + META_ROW_HEIGHT

    _draw_meta_cell(canvas, obra_l1, left, y_row1, col_w, styles["meta_info"])
    _draw_meta_cell(canvas, price_l1, left + col_w + 8, y_row1, col_w, styles["meta_info"])
    if obra_l2:
        _draw_meta_cell(canvas, obra_l2, left, y_row2, col_w, styles["meta_info"])
    _draw_meta_cell(canvas, price_l2, left + col_w + 8, y_row2, col_w, styles["meta_info"])


def draw_hline(canvas, x1: float, x2: float, y: float) -> None:
    canvas.setStrokeColor(HEADER_BLUE)
    canvas.setLineWidth(FRAME_LINE_WIDTH)
    canvas.line(x1, y, x2, y)


def draw_brasao_body_centered(canvas, doc, brasao_path: str) -> None:
    """Brasão centralizado no corpo da página (marca d'água institucional)."""
    page_w, page_h = doc.pagesize
    left = doc.leftMargin
    right = page_w - doc.rightMargin
    bottom = doc.bottomMargin
    top = page_h - doc.topMargin
    body_w = right - left
    body_h = top - bottom
    if body_w <= 0 or body_h <= 0:
        return
    cx = left + body_w / 2
    cy = bottom + body_h / 2
    size = min(body_w, body_h) * 0.42
    canvas.saveState()
    try:
        canvas.setFillAlpha(0.14)
        canvas.setStrokeAlpha(0.14)
    except Exception:
        pass
    try:
        canvas.drawImage(
            brasao_path,
            cx - size / 2,
            cy - size / 2,
            width=size,
            height=size,
            preserveAspectRatio=True,
            mask="auto",
            anchor="c",
        )
    except Exception:
        pass
    canvas.restoreState()


def draw_page_frame(canvas, doc, ctx: LandscapePdfContext) -> None:
    canvas.saveState()
    if ctx.brasao_path and ctx.brand.show_brasao:
        draw_brasao_body_centered(canvas, doc, ctx.brasao_path)
    page_w, page_h = doc.pagesize
    left = doc.leftMargin
    y_band_top = page_h - HEADER_PAD_TOP
    text_block_h = HEADER_TITLE_LEAD + len(ctx.header_lines) * HEADER_LINE_LEAD
    inner_h = text_block_h + HEADER_CONTENT_PAD_TOP + 0.06 * cm
    band_h = max(HEADER_LOGO_H, inner_h) if ctx.has_side_images else inner_h
    logo_y = y_band_top - HEADER_LOGO_H - max(0.0, (band_h - HEADER_LOGO_H) / 2)

    if ctx.logo_path:
        try:
            canvas.drawImage(
                ctx.logo_path,
                left,
                logo_y,
                width=HEADER_LOGO_W,
                height=HEADER_LOGO_H,
                preserveAspectRatio=True,
                mask="auto",
                anchor="sw",
            )
        except Exception:
            pass

    if ctx.has_side_images:
        text_y = y_band_top - (band_h - text_block_h) / 2 - 0.10 * cm
    else:
        text_y = y_band_top - HEADER_CONTENT_PAD_TOP - 0.10 * cm

    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawCentredString(page_w / 2, text_y, ctx.title)
    text_y -= HEADER_TITLE_LEAD

    canvas.setFont("Helvetica", 7)
    for line in ctx.header_lines:
        canvas.drawCentredString(page_w / 2, text_y, line[:160])
        text_y -= HEADER_LINE_LEAD

    right = page_w - doc.rightMargin
    if ctx.show_obra_meta and ctx.meta:
        header_sep_y = page_h - doc.topMargin + meta_block_height() + HEADER_GAP_AFTER_TEXT * 0.35
    else:
        header_sep_y = page_h - doc.topMargin + HEADER_GAP_AFTER_TEXT * 0.35
    draw_hline(canvas, left, right, header_sep_y)

    if ctx.show_obra_meta and ctx.meta:
        draw_obra_meta_on_canvas(canvas, doc, ctx.meta)

    canvas.setFont("Helvetica", 6.5)
    footer_base = 0.55 * cm
    addr = ctx.profile.endereco_linha()
    contact = ctx.profile.contato_linha()
    rt = ctx.brand.footer_line1 or ctx.profile.responsavel_linha()
    rt_contact = ctx.brand.footer_line2 or ctx.profile.rt_contato_linha()

    footer_lines = [ln for ln in (addr, contact, rt, rt_contact) if ln]
    if footer_lines:
        footer_sep_y = footer_base + 0.55 * cm + len(footer_lines) * 0.22 * cm + 0.10 * cm
        draw_hline(canvas, left, right, footer_sep_y)

    y = footer_base + 0.55 * cm
    if addr:
        canvas.drawCentredString(page_w / 2, y, addr[:160])
        y -= 0.22 * cm
    if contact:
        canvas.drawCentredString(page_w / 2, y, contact[:160])
        y -= 0.22 * cm
    if rt:
        canvas.drawCentredString(page_w / 2, y, rt[:160])
        y -= 0.22 * cm
    if rt_contact:
        canvas.drawCentredString(page_w / 2, y, rt_contact[:160])

    canvas.restoreState()


def cell_styles() -> dict[str, ParagraphStyle]:
    return {
        "cell": ParagraphStyle(
            "Cell",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_LEFT,
        ),
        "header": ParagraphStyle(
            "Header",
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
        "cell_bold": ParagraphStyle(
            "CellBold",
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            alignment=TA_LEFT,
        ),
        "cell_mem": ParagraphStyle(
            "CellMem",
            fontName="Helvetica-Oblique",
            fontSize=6.5,
            leading=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#444444"),
        ),
        "header_right": ParagraphStyle(
            "HeaderRight",
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            alignment=TA_RIGHT,
            textColor=colors.white,
        ),
        "cell_right": ParagraphStyle(
            "CellRight",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_RIGHT,
        ),
        "cell_center": ParagraphStyle(
            "CellCenter",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
        ),
        "cell_code": ParagraphStyle(
            "CellCode",
            fontName="Helvetica",
            fontSize=6.5,
            leading=8,
            alignment=TA_LEFT,
            splitLongWords=1,
        ),
        "meta_info": ParagraphStyle(
            "MetaInfo",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_LEFT,
        ),
    }


def para(text: str, style: ParagraphStyle, *, bold: bool = False, italic: bool = False) -> Paragraph | str:
    if not text:
        return ""
    safe = html.escape(str(text)).replace("\n", "<br/>")
    if bold:
        safe = f"<b>{safe}</b>"
    if italic:
        safe = f"<i>{safe}</i>"
    return Paragraph(safe, style)


def zebra_style_commands(
    row_count: int,
    *,
    summary_rows: int = 1,
    right_cols: tuple[int, ...] = (),
) -> list[tuple]:
    cmds: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for col in right_cols:
        cmds.append(("ALIGN", (col, 1), (col, -1), "RIGHT"))
    body_end = max(1, row_count - summary_rows)
    for row_idx in range(1, body_end):
        if row_idx % 2 == 0:
            cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), STRIPE_GRAY))
    summary_bg = colors.HexColor("#E8EEF4")
    for row_idx in range(row_count - summary_rows, row_count):
        cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), summary_bg))
        cmds.append(("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"))
    return cmds


def fmt_money(value: float | None) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def fmt_qty(value: float | None) -> str:
    """Quantidade com duas casas decimais (formato pt-BR)."""
    return fmt_money(value)


def fmt_num(value: float | None) -> str:
    if value is None:
        return ""
    try:
        v = float(value)
        if v == int(v):
            return str(int(v))
        return f"{v:.4f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return ""


def _join_meta_parts(parts: list[str]) -> str:
    return " · ".join(parts)


def _format_price_bases_summary(meta: BudgetProjectMetadata) -> str:
    bases = [b for b in (meta.price_bases or []) if b.get("enabled", True)]
    if bases:
        chunks: list[str] = []
        for base in bases:
            label = str(base.get("label") or base.get("source") or "").strip().upper()
            uf = str(base.get("uf") or "").strip()
            ref = str(base.get("reference") or "").strip()
            part = label or "BASE"
            if uf:
                part += f"/{uf}"
            if ref:
                part += f" ({ref})"
            chunks.append(part)
        return "; ".join(chunks)
    base = (meta.base_preco or "").strip()
    ref = (meta.data_ref or "").strip()
    if base and ref:
        return f"{base} ({ref})"
    return base or ref or "—"


def _format_price_bases_lines(meta: BudgetProjectMetadata) -> list[str]:
    bases = [b for b in (meta.price_bases or []) if b.get("enabled", True)]
    if not bases:
        return [_format_price_bases_summary(meta)]
    lines: list[str] = []
    for base in bases:
        label = str(base.get("label") or base.get("source") or "").strip().upper()
        uf = str(base.get("uf") or "").strip()
        ref = str(base.get("reference") or "").strip()
        part = label or "BASE"
        if uf:
            part += f"/{uf}"
        if ref:
            part += f" ({ref})"
        lines.append(part)
    return lines


def format_obra_meta_obra_lines(meta: BudgetProjectMetadata) -> tuple[str, str]:
    line1_parts: list[str] = []
    line2_parts: list[str] = []
    if meta.projeto:
        line1_parts.append(f"Obra: {meta.projeto.strip()}")
    if meta.empresa:
        line1_parts.append(f"Empresa: {meta.empresa.strip()}")
    if meta.local:
        line1_parts.append(f"Local: {meta.local.strip()}")
    if meta.objeto:
        line2_parts.append(f"Objeto: {meta.objeto.strip()}")
    if meta.orcamento:
        line2_parts.append(f"Orçamento: {meta.orcamento.strip()}")
    if meta.processo:
        line2_parts.append(f"Processo: {meta.processo.strip()}")
    return (
        _join_meta_parts(line1_parts) if line1_parts else "—",
        _join_meta_parts(line2_parts),
    )


def format_obra_meta_pricing_lines(meta: BudgetProjectMetadata) -> tuple[str, str]:
    bases = _join_meta_parts(_format_price_bases_lines(meta)) or "—"
    line1 = f"Base de preços: {bases}"
    obra_label = meta.bdi.obra_label or meta.obra_type or "RF"
    obra_type = meta.obra_type or "RF"
    com = meta.bdi.rate_com_desoneracao * 100
    sem = meta.bdi.rate_sem_desoneracao * 100
    line2 = (
        f"Tipo de obra: {obra_label} ({obra_type}) · "
        f"BDI Com D: {com:.2f}%".replace(".", ",")
        + " · "
        + f"BDI Sem D: {sem:.2f}%".replace(".", ",")
    )
    return line1, line2


def build_obra_meta_block(meta: BudgetProjectMetadata, *, usable_width: float) -> list[Any]:
    """Bloco 2×2 obra / bases acima da tabela principal."""
    styles = cell_styles()
    obra_l1, obra_l2 = format_obra_meta_obra_lines(meta)
    price_l1, price_l2 = format_obra_meta_pricing_lines(meta)
    col_w = usable_width / 2
    data = [
        [para(obra_l1, styles["meta_info"]), para(price_l1, styles["meta_info"])],
        [para(obra_l2, styles["meta_info"]) if obra_l2 else "", para(price_l2, styles["meta_info"])],
    ]
    table = Table(data, colWidths=[col_w, col_w])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 8),
                ("RIGHTPADDING", (1, 0), (1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return [Spacer(1, 3), table, Spacer(1, 5)]


def usable_landscape_width() -> float:
    return LANDSCAPE_PAGESIZE[0] - 2 * MARGIN_LR


def prepend_obra_meta(story: list[Any], meta: BudgetProjectMetadata) -> list[Any]:
    return [*build_obra_meta_block(meta, usable_width=usable_landscape_width()), *story]
