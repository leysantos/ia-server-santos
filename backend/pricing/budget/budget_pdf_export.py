"""Exportação nativa de orçamento para PDF (ReportLab) — layout profissional."""

from __future__ import annotations

import html
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from core.system.company_profile import CompanyProfile, get_company_profile, load_company_brasao, load_company_logo
from pricing.budget.budget_export_branding import (
    ExportBrandingConfig,
)
from pricing.budget.budget_pdf_landscape_template import (
    LANDSCAPE_BUDGET_DOC_TYPES,
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
from pricing.budget.budget_pdf_portrait_template import export_portrait_mcq_pdf
from pricing.budget.budget_export_tables import ExportTableData
from pricing.budget.ppd_layout import ROW_TYPE_ETAPA, ROW_TYPE_SERVICO, ROW_TYPE_SUB_ETAPA
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata

DOC_TITLES = {
    "orc_sintetico": "PLANILHA ORÇAMENTÁRIA - ORÇAMENTO SINTÉTICO",
    "orc_analitico": "PLANILHA ORÇAMENTÁRIA - ORÇAMENTO ANALÍTICO",
    "mcq": "MEMÓRIA DE CÁLCULO QUANTITATIVA",
    "cronograma": "CRONOGRAMA FÍSICO-FINANCEIRO",
    "esp_tecnica": "ESPECIFICAÇÃO TÉCNICA",
    "curva_abc": "CURVA ABC — CLASSIFICAÇÃO PARETO",
    "curva_s": "CURVA S — AVANÇO FÍSICO-FINANCEIRO",
    "histograma": "HISTOGRAMA DE DEMANDA MENSAL",
}


def export_budget_pdf(
    doc_type: str,
    roots: list[BudgetItem],
    metadata: BudgetProjectMetadata | None = None,
    *,
    branding: ExportBrandingConfig | None = None,
    schedule: Any | None = None,
    tech_spec: dict[str, Any] | None = None,
    logo_bytes: bytes | None = None,
    brasao_bytes: bytes | None = None,
    company_profile: CompanyProfile | None = None,
) -> bytes:
    key = doc_type.strip().lower()
    if key not in DOC_TITLES:
        raise ValueError(f"Tipo de documento inválido: {doc_type}")

    meta = metadata or BudgetProjectMetadata()
    profile = company_profile or get_company_profile()
    brand = branding or ExportBrandingConfig()

    if logo_bytes is None and brand.show_logo:
        logo_bytes = load_company_logo()
    if brasao_bytes is None and brand.show_brasao:
        brasao_bytes = load_company_brasao()

    title = DOC_TITLES[key]

    if key in LANDSCAPE_BUDGET_DOC_TYPES:
        return _export_landscape_budget_pdf(
            key,
            roots,
            meta=meta,
            brand=brand,
            profile=profile,
            title=title,
            logo_bytes=logo_bytes,
            brasao_bytes=brasao_bytes,
            schedule=schedule,
        )

    if key == "mcq":
        return export_portrait_mcq_pdf(
            roots,
            meta=meta,
            brand=brand,
            profile=profile,
            title=title,
            logo_bytes=logo_bytes,
            brasao_bytes=brasao_bytes,
        )

    if key == "esp_tecnica":
        return _export_portrait_pdf(
            meta,
            tech_spec=tech_spec,
            brand=brand,
            profile=profile,
            title=title,
            logo_bytes=logo_bytes,
            brasao_bytes=brasao_bytes,
        )

    raise ValueError(f"Tipo de documento inválido: {doc_type}")


def _export_landscape_budget_pdf(
    key: str,
    roots: list[BudgetItem],
    *,
    meta: BudgetProjectMetadata,
    brand: ExportBrandingConfig,
    profile: CompanyProfile,
    title: str,
    logo_bytes: bytes | None,
    brasao_bytes: bytes | None,
    schedule: Any | None,
) -> bytes:
    usable_width = usable_landscape_width()
    logo_path = write_temp_image(logo_bytes) if logo_bytes and brand.show_logo else None
    brasao_path = write_temp_image(brasao_bytes) if brasao_bytes and brand.show_brasao else None
    paths_to_cleanup = [logo_path, brasao_path]

    ctx = build_landscape_context(
        title=title,
        brand=brand,
        profile=profile,
        logo_path=logo_path,
        brasao_path=brasao_path,
        meta=meta,
        show_obra_meta=True,
    )

    if key in ("orc_sintetico", "orc_analitico"):
        story = _build_orc_table(
            roots,
            meta=meta,
            analitico=key == "orc_analitico",
            usable_width=usable_width,
        )
    elif key == "cronograma":
        story = _build_cronograma_table(roots, schedule, usable_width=usable_width)
    elif key in ("curva_abc", "curva_s", "histograma"):
        story = _build_analytics_table(key, roots, meta=meta, schedule=schedule, usable_width=usable_width)
    else:
        raise ValueError(f"Documento paisagem não suportado: {key}")

    pdf = render_landscape_pdf(story, ctx=ctx)
    cleanup_temp_images(paths_to_cleanup)
    return pdf


def _export_portrait_pdf(
    meta: BudgetProjectMetadata,
    *,
    tech_spec: dict[str, Any] | None,
    brand: ExportBrandingConfig,
    profile: CompanyProfile,
    title: str,
    logo_bytes: bytes | None,
    brasao_bytes: bytes | None,
) -> bytes:
    import io

    from reportlab.platypus import SimpleDocTemplate

    from pricing.budget.budget_pdf_landscape_template import (
        FolhaNumberedCanvas,
        MARGIN_BOTTOM,
        MARGIN_LR,
        build_landscape_context,
        draw_page_frame,
        header_top_margin,
    )

    usable_width = A4[0] - 2 * MARGIN_LR
    logo_path = write_temp_image(logo_bytes) if logo_bytes and brand.show_logo else None
    brasao_path = write_temp_image(brasao_bytes) if brasao_bytes and brand.show_brasao else None
    paths_to_cleanup = [logo_path, brasao_path]

    ctx = build_landscape_context(
        title=title,
        brand=brand,
        profile=profile,
        logo_path=logo_path,
        brasao_path=brasao_path,
    )
    top_margin = header_top_margin(ctx.has_side_images, len(ctx.header_lines))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=top_margin,
        bottomMargin=MARGIN_BOTTOM,
        leftMargin=MARGIN_LR,
        rightMargin=MARGIN_LR,
        title=title,
    )

    story = _build_esp_story(meta, tech_spec, usable_width=usable_width)

    def on_page(canvas, doc_template):
        draw_page_frame(canvas, doc_template, ctx)

    doc.build(
        story,
        onFirstPage=on_page,
        onLaterPages=on_page,
        canvasmaker=FolhaNumberedCanvas,
    )
    cleanup_temp_images(paths_to_cleanup)
    return buffer.getvalue()


def _flatten_budget_rows(
    roots: list[BudgetItem],
    *,
    include_memory: bool = True,
) -> list[tuple[BudgetItem, int]]:
    rows: list[tuple[BudgetItem, int]] = []

    def walk(node: BudgetItem, depth: int) -> None:
        rows.append((node, depth))
        for child in node.children:
            is_memory = child.metadata.get("is_memory_row") or child.row_type == "MEMORIA"
            if is_memory:
                if include_memory:
                    rows.append((child, depth + 1))
                continue
            walk(child, depth + 1)

    for root in roots:
        walk(root, 0)
    return rows


def _orc_col_widths(usable_width: float, analitico: bool) -> list[float]:
    if analitico:
        fracs = [0.05, 0.07, 0.11, 0.40, 0.05, 0.06, 0.13, 0.13]
    else:
        fracs = [0.05, 0.15, 0.43, 0.05, 0.06, 0.13, 0.13]
    return [usable_width * f for f in fracs]


_CPU_TIPO_LABELS: dict[str, str] = {
    "mao_obra": "M.O.",
    "insumo": "Material",
    "equipamento": "Equip.",
    "composicao": "Comp.",
    "atividade": "Ativ.",
    "tempo_fixo": "T.Fixo",
    "transporte": "Transp.",
    "fic": "FIC",
}


def _budget_desoneracao_mode(roots: list[BudgetItem]) -> str:
    """Cenário adotado (menor total ComD vs SemD) — mesma regra do orç. sintético."""
    comd = round(sum(r.total_price for r in roots), 2)
    semd = round(sum(r.total_price_semd for r in roots), 2)
    if semd > 0 and semd < comd:
        return "semd"
    return "comd"


def _price_headers(mode: str) -> tuple[str, str]:
    if mode == "semd":
        return "Unit. Sem D", "Total Sem D"
    return "Unit. Com D", "Total Com D"


def _budget_row_tipo(item: BudgetItem, *, is_group: bool) -> str:
    if item.row_type == ROW_TYPE_ETAPA or (is_group and item.level == 0):
        return "Etapa"
    if item.row_type == ROW_TYPE_SUB_ETAPA:
        return "Sub-etapa"
    return "Serviço"


def _cpu_tipo_label(item_type: str | None) -> str:
    key = str(item_type or "").strip().lower()
    if not key:
        return ""
    return _CPU_TIPO_LABELS.get(key, key.replace("_", " ").title()[:12])


def _item_unit_for_mode(item: BudgetItem, mode: str) -> float | None:
    value = item.unit_price_semd if mode == "semd" else item.unit_price
    return float(value) if value else None


def _item_total_for_mode(item: BudgetItem, mode: str) -> float | None:
    value = item.total_price_semd if mode == "semd" else item.total_price
    return float(value) if value else None


def _direct_cost_total(roots: list[BudgetItem], mode: str) -> float:
    def walk(item: BudgetItem) -> float:
        if _is_service_row(item):
            qty = float(item.quantity or 0)
            if mode == "semd":
                unit_cost = item.unit_cost_semd or item.unit_cost
                total_bdi = item.total_price_semd
            else:
                unit_cost = item.unit_cost
                total_bdi = item.total_price
            if unit_cost and qty:
                return round(float(unit_cost) * qty, 2)
            rate = item.bdi_rate
            if mode == "semd":
                rate = float(item.metadata.get("bdi_rate_semd") or rate)
            if total_bdi and rate:
                return round(float(total_bdi) / (1 + float(rate)), 2)
            return 0.0
        return round(sum(walk(c) for c in item.children), 2)

    return round(sum(walk(r) for r in roots), 2)


def _grand_total_for_mode(roots: list[BudgetItem], mode: str) -> float:
    if mode == "semd":
        return round(sum(r.total_price_semd for r in roots), 2)
    return round(sum(r.total_price for r in roots), 2)


def _is_service_row(item: BudgetItem) -> bool:
    return (
        item.row_type in (ROW_TYPE_SERVICO, "SERVICO")
        or item.item_type.value == "composition"
    )


def _money_right(styles: dict[str, ParagraphStyle], value: float | None) -> Paragraph | str:
    text = fmt_money(value)
    return para(text, styles["cell_right"]) if text else ""


def _qty_right(styles: dict[str, ParagraphStyle], value: float | None) -> Paragraph | str:
    text = fmt_num(value)
    return para(text, styles["cell_right"]) if text else ""


def _norm_price_source(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _is_seminf_composition_code(code: str) -> bool:
    return code.lower().endswith(".seminf")


def _meta_default_uf(meta: BudgetProjectMetadata) -> str:
    for base in meta.price_bases or []:
        if base.get("enabled") and base.get("uf"):
            return str(base["uf"]).strip().upper()
    local = (meta.local or "").strip()
    if "/" in local:
        uf = local.rsplit("/", 1)[-1].strip().upper()
        if len(uf) == 2:
            return uf
    return "SP"


def _resolve_open_composition_lookup(
    item: BudgetItem,
    meta: BudgetProjectMetadata,
) -> tuple[str, str] | None:
    enabled = [
        b for b in (meta.price_bases or []) if b.get("enabled") and b.get("reference")
    ]
    uf = _meta_default_uf(meta)
    code = (item.source_code or "").strip()
    if not code:
        return None

    if not enabled:
        from pricing.budget.price_bank_index import PriceBankIndex

        ref = PriceBankIndex.load().active_reference
        return (ref, uf) if ref else None

    if _is_seminf_composition_code(code):
        for base in enabled:
            src = _norm_price_source(str(base.get("source") or base.get("label") or ""))
            if src in ("dpseminf", "ppdseminf", "seminf"):
                return str(base["reference"]), str(base.get("uf") or uf).upper()
        return str(enabled[0]["reference"]), str(enabled[0].get("uf") or uf).upper()

    raw = (item.source_base or "").strip()
    if raw:
        key = _norm_price_source(raw)
        for base in enabled:
            src = _norm_price_source(str(base.get("source") or ""))
            label = _norm_price_source(str(base.get("label") or ""))
            if key in (src, label) or src in key or label in key:
                return str(base["reference"]), str(base.get("uf") or uf).upper()

    first = enabled[0]
    return str(first["reference"]), str(first.get("uf") or uf).upper()


def _fetch_open_composition_items(
    code: str,
    lookup: tuple[str, str],
    cache: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ref, uf = lookup
    key = (code, ref, uf)
    if key in cache:
        return cache[key]
    try:
        from pricing.tools.budget_pricing_tools import BudgetPricingTools

        comp = BudgetPricingTools.get_open_composition(code, uf=uf, reference=ref)
        items = list(comp.get("items") or [])
    except (ValueError, OSError, KeyError):
        items = []
    cache[key] = items
    return items


def _analitico_cpu_row(
    cpu_item: dict[str, Any],
    depth: int,
    styles: dict[str, ParagraphStyle],
    *,
    mode: str,
) -> list[Any]:
    indent = "  " * depth
    desc = f"{indent}{cpu_item.get('description') or ''}"
    if mode == "semd":
        unit_price = cpu_item.get("unit_price_sem")
        if unit_price is None:
            unit_price = cpu_item.get("unit_price")
        partial = cpu_item.get("partial_cost_sem")
        if partial is None:
            partial = cpu_item.get("partial_cost")
    else:
        unit_price = cpu_item.get("unit_price")
        partial = cpu_item.get("partial_cost")
    return [
        "",
        para(_cpu_tipo_label(str(cpu_item.get("item_type") or "")), styles["cell_center"]),
        para(str(cpu_item.get("code") or ""), styles["cell_code"]),
        para(desc, styles["cell_mem"]),
        para(str(cpu_item.get("unit") or ""), styles["cell_center"]),
        _qty_right(styles, cpu_item.get("coefficient")),
        _money_right(styles, unit_price),
        _money_right(styles, partial),
    ]


def _build_orc_table(
    roots: list[BudgetItem],
    *,
    meta: BudgetProjectMetadata,
    analitico: bool,
    usable_width: float,
) -> list[Any]:
    styles = cell_styles()
    adopted_mode = _budget_desoneracao_mode(roots)
    unit_hdr, total_hdr = _price_headers(adopted_mode)

    if analitico:
        header = ["Item", "Tipo", "Código", "Descrição", "Un", "Qtd", unit_hdr, total_hdr]
    else:
        header = ["Item", "Código", "Descrição", "Un", "Qtd", unit_hdr, total_hdr]

    header_cells: list[Any] = []
    for idx, h in enumerate(header):
        right_idx = {5, 6, 7} if analitico else {4, 5, 6}
        if idx in right_idx:
            header_cells.append(para(h, styles["header_right"]))
        else:
            header_cells.append(para(h, styles["header"]))
    data: list[list[Any]] = [header_cells]

    right_cols = (5, 6, 7) if analitico else (4, 5, 6)
    comp_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    for item, depth in _flatten_budget_rows(roots, include_memory=False):
        indent = "  " * depth
        is_group = item.row_type in (ROW_TYPE_ETAPA, ROW_TYPE_SUB_ETAPA) or (
            item.item_type.value == "group" and item.level == 0
        )
        desc = f"{indent}{item.name or ''}"
        source_code = "" if is_group else (item.source_code or "")
        unit_price = _item_unit_for_mode(item, adopted_mode) if not is_group else None
        line_total = (
            _item_total_for_mode(item, adopted_mode)
            if is_group or _is_service_row(item)
            else None
        )

        if analitico:
            row = [
                para(item.code or "", styles["cell_bold"] if is_group else styles["cell"]),
                para(_budget_row_tipo(item, is_group=is_group), styles["cell_center"]),
                para(source_code, styles["cell_code"]) if source_code else "",
                para(desc, styles["cell_bold"] if is_group else styles["cell"], bold=is_group),
                para(item.unit or "", styles["cell_center"]) if not is_group and item.unit else "",
                _money_right(styles, item.quantity) if not is_group else "",
                _money_right(styles, unit_price) if not is_group else "",
                _money_right(styles, line_total),
            ]
        else:
            row = [
                para(item.code or "", styles["cell_bold"] if is_group else styles["cell"]),
                para(source_code, styles["cell_code"]) if source_code else "",
                para(desc, styles["cell_bold"] if is_group else styles["cell"], bold=is_group),
                para(item.unit or "", styles["cell_center"]) if not is_group and item.unit else "",
                _money_right(styles, item.quantity) if not is_group else "",
                _money_right(styles, unit_price) if not is_group else "",
                _money_right(styles, line_total),
            ]
        data.append(row)

        if analitico and _is_service_row(item) and source_code:
            lookup = _resolve_open_composition_lookup(item, meta)
            if lookup:
                for cpu_item in _fetch_open_composition_items(source_code, lookup, comp_cache):
                    data.append(
                        _analitico_cpu_row(cpu_item, depth + 1, styles, mode=adopted_mode)
                    )

    direct_cost = _direct_cost_total(roots, adopted_mode)
    grand_total = _grand_total_for_mode(roots, adopted_mode)
    bdi_valor = round(grand_total - direct_cost, 2)
    bdi_rate = (
        meta.bdi.rate_sem_desoneracao if adopted_mode == "semd" else meta.bdi.rate_com_desoneracao
    )
    bdi_label = f"BDI ({bdi_rate * 100:.2f}%)".replace(".", ",")

    desc_col = 3 if analitico else 2
    total_col = 7 if analitico else 6
    col_count = 8 if analitico else 7

    def _summary_row(label: str, amount: float) -> list[Any]:
        cells: list[Any] = [""] * col_count
        cells[desc_col] = para(label, styles["cell_bold"], bold=True)
        cells[total_col] = _money_right(styles, amount)
        return cells

    data.append(_summary_row("TOTAL SEM BDI", direct_cost))
    data.append(_summary_row(bdi_label, bdi_valor))
    data.append(_summary_row("TOTAL COM BDI", grand_total))

    table = Table(data, colWidths=_orc_col_widths(usable_width, analitico), repeatRows=1)
    table.setStyle(TableStyle(zebra_style_commands(len(data), summary_rows=3, right_cols=right_cols)))
    return [table]


def _build_analytics_table(
    doc_type: str,
    roots: list[BudgetItem],
    *,
    meta: BudgetProjectMetadata,
    schedule: Any | None,
    usable_width: float,
) -> list[Any]:
    from pricing.budget.budget_export_tables import build_export_table
    from pricing.budget.budget_pdf_charts import (
        analytics_chart_caption,
        analytics_chart_legend,
        build_analytics_chart_flowable,
    )

    table_data, extra_line, _ = build_export_table(
        doc_type, roots, meta, schedule=schedule
    )
    if not table_data:
        raise ValueError(f"Sem dados para exportar: {doc_type}")

    story: list[Any] = []
    styles = cell_styles()
    if extra_line:
        story.append(Paragraph(f"<b>{html.escape(extra_line)}</b>", styles["cell"]))
        story.append(Spacer(1, 6))

    chart, include_bdi_ref = build_analytics_chart_flowable(
        doc_type,
        roots,
        meta=meta,
        schedule=schedule,
        width=usable_width,
    )
    if chart:
        story.append(chart)
        legend_items = analytics_chart_legend(doc_type, include_bdi_ref=include_bdi_ref)
        if legend_items:
            story.extend(_build_chart_legend_rows(legend_items, usable_width))
        caption = analytics_chart_caption(doc_type)
        if caption:
            story.append(Spacer(1, 2))
            story.append(
                Paragraph(
                    f'<font size="7" color="#64748b">{html.escape(caption)}</font>',
                    styles["cell"],
                )
            )
        story.append(Spacer(1, 10))

    col_count = len(table_data.headers)
    fracs = _analytics_col_fracs(doc_type, col_count)
    col_widths = [usable_width * f for f in fracs]

    header_cells = [
        para(h, styles["header_right"] if i in table_data.right_cols else styles["header"])
        for i, h in enumerate(table_data.headers)
    ]
    data: list[list[Any]] = [header_cells]

    for row_idx, row in enumerate(table_data.rows):
        is_bold = row_idx in table_data.bold_rows
        cells: list[Any] = []
        for col_idx, cell in enumerate(row):
            text = str(cell) if cell is not None else ""
            if col_idx in table_data.right_cols:
                style = styles["cell_bold"] if is_bold else styles["cell_right"]
            else:
                style = styles["cell_bold"] if is_bold else styles["cell"]
            cells.append(para(text, style, bold=is_bold) if text else "")
        data.append(cells)

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            zebra_style_commands(
                len(data),
                summary_rows=table_data.summary_rows,
                right_cols=table_data.right_cols,
            )
        )
    )
    story.append(table)
    return story


def _build_chart_legend_rows(
    items: list[tuple[str, str]],
    usable_width: float,
) -> list[Any]:
    """Legenda horizontal com marcadores coloridos — espelho do ChartLegend do frontend."""
    del usable_width
    styles = cell_styles()
    parts: list[str] = []
    for label, color_hex in items:
        parts.append(
            f'<font color="{color_hex}">■</font> '
            f'<font size="8" color="#64748b">{html.escape(label)}</font>&nbsp;&nbsp;&nbsp;'
        )
    return [Spacer(1, 4), Paragraph("".join(parts), styles["cell"])]


def _analytics_col_fracs(doc_type: str, col_count: int) -> list[float]:
    key = doc_type.strip().lower()
    if key == "curva_abc" and col_count == 7:
        return [0.06, 0.10, 0.38, 0.14, 0.10, 0.12, 0.10]
    if key == "curva_s" and col_count == 7:
        return [0.14, 0.08, 0.12, 0.12, 0.16, 0.18, 0.20]
    if key == "histograma" and col_count == 7:
        return [0.14, 0.08, 0.14, 0.14, 0.14, 0.14, 0.14]
    return [1.0 / col_count] * col_count


def _build_cronograma_table(
    roots: list[BudgetItem],
    schedule: Any | None,
    *,
    usable_width: float,
) -> list[Any]:
    from pricing.budget.ppd_exporter import _schedule_total_days

    story: list[Any] = []
    styles = cell_styles()
    prazo = _schedule_total_days(schedule)
    if prazo:
        story.append(Paragraph(f"<b>Prazo de execução:</b> {prazo} dias", styles["cell"]))
        story.append(Spacer(1, 6))

    header = ["Etapa", "Descrição", "Valor (R$)"]
    data: list[list[Any]] = [[para(h, styles["header"]) for h in header]]
    for root in roots:
        if root.row_type != ROW_TYPE_ETAPA and root.level != 0:
            continue
        code = root.code if "." in str(root.code) else f"{root.code}.0"
        total = root.total_price or root.effective_total()
        data.append([
            code,
            para(root.name or "", styles["cell"]),
            para(fmt_money(total), styles["cell_right"]),
        ])

    col_widths = [usable_width * 0.12, usable_width * 0.68, usable_width * 0.20]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle(zebra_style_commands(len(data), summary_rows=0, right_cols=(2,))))
    story.append(table)
    return story


def _build_esp_story(
    meta: BudgetProjectMetadata,
    tech_spec: dict[str, Any] | None,
    *,
    usable_width: float,
) -> list[Any]:
    from pricing.spec.tech_spec_models import TechSpecDocument

    body_style = ParagraphStyle("EspBody", fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT)
    doc = TechSpecDocument.from_dict(tech_spec) if tech_spec else None
    story: list[Any] = []

    if doc and doc.title:
        story.append(Paragraph(f"<b>{html.escape(doc.title)}</b>", body_style))
        story.append(Spacer(1, 8))

    body = (doc.markdown or "").strip() if doc else ""
    if not body:
        story.append(Paragraph("(Conteúdo não gerado — use a aba Especificação no orçamento)", body_style))
        return story

    for line in body.splitlines():
        text = line.strip()
        if text.startswith("#"):
            level = len(text) - len(text.lstrip("#"))
            text = text.lstrip("# ").strip()
            size = max(10, 14 - level)
            story.append(Paragraph(f"<b>{html.escape(text)}</b>", ParagraphStyle("H", parent=body_style, fontSize=size)))
        elif text:
            story.append(Paragraph(html.escape(text), body_style))
        else:
            story.append(Spacer(1, 4))

    return story
