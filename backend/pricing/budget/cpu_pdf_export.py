"""Export PDF da CPU consultada (composição aberta standalone)."""

from __future__ import annotations

import html
from typing import Any, Literal

from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from core.system.company_profile import get_company_profile, load_company_brasao, load_company_logo
from core.system.export_branding_store import get_global_export_branding
from pricing.budget.budget_export_tables import _cpu_tipo_label
from pricing.budget.budget_pdf_landscape_template import (
    build_landscape_context,
    cell_styles,
    cleanup_temp_images,
    fmt_money,
    fmt_num,
    para,
    render_landscape_pdf,
    usable_landscape_width,
    write_temp_image,
    zebra_style_commands,
)

PriceMode = Literal["comd", "semd"]

_HEADER = ["Tipo", "Código", "Descrição", "Un", "Coeficiente", "Unitário (R$)", "Parcial (R$)"]
_CENTER_COLS = (0, 1, 3)
_RIGHT_COLS = (4, 5, 6)


def _item_values(item: dict[str, Any], mode: PriceMode) -> tuple[float | None, float | None]:
    if mode == "semd":
        unit = item.get("unit_price_sem")
        if unit is None:
            unit = item.get("unit_price")
        partial = item.get("partial_cost_sem")
        if partial is None:
            partial = item.get("partial_cost")
    else:
        unit = item.get("unit_price")
        partial = item.get("partial_cost")
    return unit, partial


def _cpu_row(item: dict[str, Any], styles: dict, *, mode: PriceMode) -> list[Any]:
    unit, partial = _item_values(item, mode)
    return [
        para(_cpu_tipo_label(str(item.get("item_type") or "")), styles["cell_center"]),
        para(str(item.get("code") or ""), styles["cell_center"]),
        para(str(item.get("description") or ""), styles["cell"]),
        para(str(item.get("unit") or ""), styles["cell_center"]),
        para(fmt_num(item.get("coefficient")), styles["cell_right"]) if item.get("coefficient") is not None else "",
        para(fmt_money(unit), styles["cell_right"]) if unit is not None else "",
        para(fmt_money(partial), styles["cell_right"]) if partial is not None else "",
    ]


def _meta_block(comp: dict[str, Any], *, mode: PriceMode, reference_label: str | None) -> list[Any]:
    styles = cell_styles()
    code = str(comp.get("code") or "")
    desc = str(comp.get("description") or "")
    unit = str(comp.get("unit") or "")
    uf = str(comp.get("price_uf") or comp.get("uf") or "")
    ref = reference_label or str(comp.get("reference") or "")
    if mode == "semd":
        total = comp.get("total_price_sem") or comp.get("analytical_total_sem") or comp.get("total_price")
    else:
        total = comp.get("total_price") or comp.get("analytical_total_com")

    lines = [
        f"<b>Código:</b> {html.escape(code)} · <b>Unidade:</b> {html.escape(unit)}",
        f"<b>Descrição:</b> {html.escape(desc)}",
        f"<b>Referência:</b> {html.escape(ref)} · <b>UF:</b> {html.escape(uf)} · "
        f"<b>Total ({'SemD' if mode == 'semd' else 'ComD'}):</b> R$ {html.escape(fmt_money(total))}",
    ]
    if comp.get("grupo"):
        lines.append(f"<b>Grupo:</b> {html.escape(str(comp['grupo']))}")
    if comp.get("tp2"):
        lines.append(f"<b>%AS / tp2:</b> {html.escape(str(comp['tp2']))}")

    blocks: list[Any] = []
    for line in lines:
        blocks.append(Paragraph(line, styles["meta_info"]))
        blocks.append(Spacer(1, 2))
    blocks.append(Spacer(1, 6))
    return blocks


def _build_cpu_table(comp: dict[str, Any], *, mode: PriceMode, usable_width: float) -> list[Any]:
    styles = cell_styles()
    header_cells: list[Any] = []
    for idx, label in enumerate(_HEADER):
        if idx in _RIGHT_COLS:
            header_cells.append(para(label, styles["header_right"]))
        elif idx in _CENTER_COLS:
            header_cells.append(para(label, styles["header"]))
        else:
            header_cells.append(para(label, styles["header_left"]))

    rows: list[list[Any]] = [header_cells]
    items = list(comp.get("items") or [])
    for item in items:
        rows.append(_cpu_row(item, styles, mode=mode))

    if mode == "semd":
        total_val = comp.get("total_price_sem") or comp.get("analytical_total_sem") or comp.get("total_price")
    else:
        total_val = comp.get("total_price") or comp.get("analytical_total_com")

    summary = ["", "", "TOTAL", "", "", "", fmt_money(total_val)]
    summary_cells: list[Any] = []
    for idx, text in enumerate(summary):
        style = (
            styles["cell_right"]
            if idx in _RIGHT_COLS
            else styles["cell_center"]
            if idx in _CENTER_COLS
            else styles["cell"]
        )
        summary_cells.append(para(str(text), style, bold=True) if text else "")
    rows.append(summary_cells)

    fracs = [0.08, 0.10, 0.38, 0.06, 0.10, 0.14, 0.14]
    col_widths = [usable_width * f for f in fracs]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            zebra_style_commands(
                len(rows),
                summary_rows=1,
                right_cols=_RIGHT_COLS,
                center_cols=_CENTER_COLS,
            )
        )
    )
    return [table]


def export_open_composition_pdf(
    comp: dict[str, Any],
    *,
    mode: PriceMode = "comd",
    reference_label: str | None = None,
) -> bytes:
    """Gera PDF paisagem institucional da CPU consultada."""
    branding = get_global_export_branding()
    profile = get_company_profile()
    logo_bytes = load_company_logo() if branding.show_logo else None
    brasao_bytes = load_company_brasao() if branding.show_brasao else None
    logo_path = write_temp_image(logo_bytes) if logo_bytes else None
    brasao_path = write_temp_image(brasao_bytes) if brasao_bytes else None
    paths = [logo_path, brasao_path]

    code = str(comp.get("code") or "CPU")
    ctx = build_landscape_context(
        title=f"CPU {code} — COMPOSIÇÃO DE PREÇOS UNITÁRIOS",
        brand=branding,
        profile=profile,
        logo_path=logo_path,
        brasao_path=brasao_path,
    )

    usable = usable_landscape_width()
    story = _meta_block(comp, mode=mode, reference_label=reference_label)
    story.extend(_build_cpu_table(comp, mode=mode, usable_width=usable))

    pdf = render_landscape_pdf(story, ctx=ctx)
    cleanup_temp_images(paths)
    return pdf
