"""Template PDF retrato A4 para documentos de orçamento (modelo memória de cálculo).

Aplicável a: mcq (memória de cálculo quantitativa).

Configuração congelada (portrait_budget_v1):
- Folha A4 vertical
- Cabeçalho/rodapé institucional (logo no canto, título, endereço, numeração de folhas)
- Brasão centralizado no corpo da página (marca d'água)
- Bloco obra/bases 2×2 acima da tabela (Obra, Empresa, Local | Base de preços; Objeto, Orçamento | Tipo obra, BDI)
- Tabela MCQ: Item, Código, Descrição, Un, Qtd (sem BDI)
- Larguras: Item 7% · Código 18% · Descrição 54% · Un 7% · Qtd 14%
- Quantidade com duas casas decimais (formato pt-BR)
"""

from __future__ import annotations

from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle

from core.system.company_profile import CompanyProfile
from pricing.budget.budget_export_branding import ExportBrandingConfig
from pricing.budget.budget_export_tables import flatten_budget_rows
from pricing.budget.budget_pdf_landscape_template import (
    FolhaNumberedCanvas,
    LandscapePdfContext,
    MARGIN_BOTTOM,
    MARGIN_LR,
    build_landscape_context,
    cell_styles,
    cleanup_temp_images,
    draw_page_frame,
    fmt_qty,
    header_top_margin,
    meta_block_height,
    para,
    write_temp_image,
    zebra_style_commands,
)
from pricing.budget.ppd_layout import ROW_TYPE_ETAPA, ROW_TYPE_SUB_ETAPA
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata

TEMPLATE_ID = "portrait_budget_v1"

PORTRAIT_BUDGET_DOC_TYPES = frozenset({"mcq"})

PORTRAIT_PAGESIZE = A4

# Item · Código · Descrição · Un · Qtd
MCQ_COL_FRACS: tuple[float, ...] = (0.07, 0.18, 0.54, 0.07, 0.14)

MCQ_TABLE_HEADERS: tuple[str, ...] = ("Item", "Código", "Descrição", "Un", "Qtd")

PortraitPdfContext = LandscapePdfContext


def usable_portrait_width() -> float:
    return PORTRAIT_PAGESIZE[0] - 2 * MARGIN_LR


def build_portrait_context(
    *,
    title: str,
    brand: ExportBrandingConfig,
    profile: CompanyProfile,
    logo_path: str | None,
    brasao_path: str | None,
    meta: BudgetProjectMetadata | None = None,
    show_obra_meta: bool = False,
) -> PortraitPdfContext:
    return build_landscape_context(
        title=title,
        brand=brand,
        profile=profile,
        logo_path=logo_path,
        brasao_path=brasao_path,
        meta=meta,
        show_obra_meta=show_obra_meta,
    )


def portrait_top_margin(ctx: PortraitPdfContext) -> float:
    top = header_top_margin(ctx.has_side_images, len(ctx.header_lines))
    if ctx.show_obra_meta and ctx.meta:
        top += meta_block_height()
    return top


def render_portrait_pdf(
    story: list[Any],
    *,
    ctx: PortraitPdfContext,
) -> bytes:
    import io

    from reportlab.platypus import SimpleDocTemplate

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PORTRAIT_PAGESIZE,
        topMargin=portrait_top_margin(ctx),
        bottomMargin=MARGIN_BOTTOM,
        leftMargin=MARGIN_LR,
        rightMargin=MARGIN_LR,
        title=ctx.title,
    )

    def on_page(canvas, doc_template):
        draw_page_frame(canvas, doc_template, ctx)

    doc.build(
        story,
        onFirstPage=on_page,
        onLaterPages=on_page,
        canvasmaker=FolhaNumberedCanvas,
    )
    return buffer.getvalue()


def mcq_col_widths(usable_width: float | None = None) -> list[float]:
    width = usable_width if usable_width is not None else usable_portrait_width()
    return [width * frac for frac in MCQ_COL_FRACS]


def build_mcq_table(roots: list[BudgetItem], *, usable_width: float | None = None) -> list[Any]:
    width = usable_width if usable_width is not None else usable_portrait_width()
    styles = cell_styles()
    data: list[list[Any]] = [[para(h, styles["header"]) for h in MCQ_TABLE_HEADERS]]

    for item, depth in flatten_budget_rows(roots):
        if item.metadata.get("is_memory_row") or item.row_type == "MEMORIA":
            mem = f"{'  ' * depth}{item.calculation_note or item.name or ''}"
            data.append(["", "", para(mem, styles["cell_mem"], italic=True), "", ""])
            continue
        is_group = item.row_type in (ROW_TYPE_ETAPA, ROW_TYPE_SUB_ETAPA)
        data.append([
            item.code or "",
            "" if is_group else (item.source_code or ""),
            para(
                f"{'  ' * depth}{item.name or ''}",
                styles["cell_bold"] if is_group else styles["cell"],
                bold=is_group,
            ),
            "" if is_group else (item.unit or ""),
            "" if is_group else fmt_qty(item.quantity),
        ])

    table = Table(data, colWidths=mcq_col_widths(width), repeatRows=1)
    table.setStyle(TableStyle(zebra_style_commands(len(data), summary_rows=0, right_cols=(4,))))
    return [table]


def export_portrait_mcq_pdf(
    roots: list[BudgetItem],
    *,
    meta: BudgetProjectMetadata,
    brand: ExportBrandingConfig,
    profile: CompanyProfile,
    title: str,
    logo_bytes: bytes | None,
    brasao_bytes: bytes | None = None,
) -> bytes:
    logo_path = write_temp_image(logo_bytes) if logo_bytes and brand.show_logo else None
    brasao_path = write_temp_image(brasao_bytes) if brasao_bytes and brand.show_brasao else None
    paths_to_cleanup = [logo_path, brasao_path]

    ctx = build_portrait_context(
        title=title,
        brand=brand,
        profile=profile,
        logo_path=logo_path,
        brasao_path=brasao_path,
        meta=meta,
        show_obra_meta=True,
    )
    story = build_mcq_table(roots)
    pdf = render_portrait_pdf(story, ctx=ctx)
    cleanup_temp_images(paths_to_cleanup)
    return pdf
