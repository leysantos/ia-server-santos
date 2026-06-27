"""Dados tabulares compartilhados entre exportação PDF e Excel (mesmo layout)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pricing.budget.budget_pdf_landscape_template import fmt_money, fmt_num
from pricing.budget.ppd_layout import ROW_TYPE_ETAPA, ROW_TYPE_SERVICO, ROW_TYPE_SUB_ETAPA
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata

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


@dataclass
class ExportTableData:
    headers: list[str]
    rows: list[list[Any]]
    right_cols: tuple[int, ...] = ()
    summary_rows: int = 0
    bold_rows: set[int] = field(default_factory=set)


def flatten_budget_rows(
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


def budget_desoneracao_mode(roots: list[BudgetItem]) -> str:
    comd = round(sum(r.total_price for r in roots), 2)
    semd = round(sum(r.total_price_semd for r in roots), 2)
    if semd > 0 and semd < comd:
        return "semd"
    return "comd"


def _price_headers(mode: str) -> tuple[str, str]:
    if mode == "semd":
        return "Unit. Sem D", "Total Sem D"
    return "Unit. Com D", "Total Com D"


def _is_service_row(item: BudgetItem) -> bool:
    return (
        item.row_type in (ROW_TYPE_SERVICO, "SERVICO")
        or item.item_type.value == "composition"
    )


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
    enabled = [b for b in (meta.price_bases or []) if b.get("enabled") and b.get("reference")]
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


def _cell_money(value: float | None) -> str:
    return fmt_money(value) if value is not None else ""


def _cell_qty(value: float | None) -> str:
    return fmt_num(value) if value is not None else ""


def _analitico_cpu_row_plain(
    cpu_item: dict[str, Any],
    depth: int,
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
        _cpu_tipo_label(str(cpu_item.get("item_type") or "")),
        str(cpu_item.get("code") or ""),
        desc,
        str(cpu_item.get("unit") or ""),
        _cell_qty(cpu_item.get("coefficient")),
        _cell_money(unit_price),
        _cell_money(partial),
    ]


def build_orc_export_table(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    *,
    analitico: bool,
) -> ExportTableData:
    adopted_mode = budget_desoneracao_mode(roots)
    unit_hdr, total_hdr = _price_headers(adopted_mode)
    if analitico:
        headers = ["Item", "Tipo", "Código", "Descrição", "Un", "Qtd", unit_hdr, total_hdr]
    else:
        headers = ["Item", "Código", "Descrição", "Un", "Qtd", unit_hdr, total_hdr]

    rows: list[list[Any]] = []
    bold_rows: set[int] = set()
    comp_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    for item, depth in flatten_budget_rows(roots, include_memory=False):
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

        if is_group:
            bold_rows.add(len(rows))

        if analitico:
            rows.append([
                item.code or "",
                _budget_row_tipo(item, is_group=is_group),
                source_code,
                desc,
                item.unit or "" if not is_group and item.unit else "",
                _cell_qty(item.quantity) if not is_group else "",
                _cell_money(unit_price) if not is_group else "",
                _cell_money(line_total),
            ])
        else:
            rows.append([
                item.code or "",
                source_code,
                desc,
                item.unit or "" if not is_group and item.unit else "",
                _cell_qty(item.quantity) if not is_group else "",
                _cell_money(unit_price) if not is_group else "",
                _cell_money(line_total),
            ])

        if analitico and _is_service_row(item) and source_code:
            lookup = _resolve_open_composition_lookup(item, meta)
            if lookup:
                for cpu_item in _fetch_open_composition_items(source_code, lookup, comp_cache):
                    rows.append(_analitico_cpu_row_plain(cpu_item, depth + 1, mode=adopted_mode))

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
        cells[desc_col] = label
        cells[total_col] = _cell_money(amount)
        return cells

    rows.append(_summary_row("TOTAL SEM BDI", direct_cost))
    rows.append(_summary_row(bdi_label, bdi_valor))
    rows.append(_summary_row("TOTAL COM BDI", grand_total))
    for offset in range(3):
        bold_rows.add(len(rows) - 3 + offset)

    right_cols = (5, 6, 7) if analitico else (4, 5, 6)
    return ExportTableData(
        headers=headers,
        rows=rows,
        right_cols=right_cols,
        summary_rows=3,
        bold_rows=bold_rows,
    )


def build_mcq_export_table(roots: list[BudgetItem]) -> ExportTableData:
    headers = ["Item", "Código", "Descrição", "Un", "Qtd"]
    rows: list[list[Any]] = []
    bold_rows: set[int] = set()

    for item, depth in flatten_budget_rows(roots):
        if item.metadata.get("is_memory_row") or item.row_type == "MEMORIA":
            mem = f"{'  ' * depth}{item.calculation_note or item.name or ''}"
            rows.append(["", "", mem, "", ""])
            continue
        is_group = item.row_type in (ROW_TYPE_ETAPA, ROW_TYPE_SUB_ETAPA)
        if is_group:
            bold_rows.add(len(rows))
        rows.append([
            item.code or "",
            "" if is_group else (item.source_code or ""),
            f"{'  ' * depth}{item.name or ''}",
            "" if is_group else (item.unit or ""),
            "" if is_group else _cell_qty(item.quantity),
        ])

    return ExportTableData(headers=headers, rows=rows, right_cols=(4,), bold_rows=bold_rows)


def build_cronograma_export_table(
    roots: list[BudgetItem],
    schedule: Any | None,
) -> tuple[str | None, ExportTableData]:
    from pricing.budget.ppd_exporter import _schedule_total_days

    prazo = _schedule_total_days(schedule)
    prazo_label = f"Prazo de execução: {prazo} dias" if prazo else None
    headers = ["Etapa", "Descrição", "Valor (R$)"]
    rows: list[list[Any]] = []
    for root in roots:
        if root.row_type != ROW_TYPE_ETAPA and root.level != 0:
            continue
        code = root.code if "." in str(root.code) else f"{root.code}.0"
        total = root.total_price or root.effective_total()
        rows.append([code, root.name or "", _cell_money(total)])
    return prazo_label, ExportTableData(headers=headers, rows=rows, right_cols=(2,))


def build_esp_tecnica_body_lines(tech_spec: dict[str, Any] | None) -> list[str]:
    from pricing.spec.tech_spec_models import TechSpecDocument

    doc = TechSpecDocument.from_dict(tech_spec) if tech_spec else None
    lines: list[str] = []
    if doc and doc.title:
        lines.append(doc.title)
        lines.append("")
    body = (doc.markdown or "").strip() if doc else ""
    if not body:
        lines.append("(Conteúdo não gerado — use a aba Especificação no orçamento)")
        return lines
    for line in body.splitlines():
        text = line.strip()
        if text.startswith("#"):
            text = text.lstrip("# ").strip()
            lines.append(text)
        elif text:
            lines.append(text)
        else:
            lines.append("")
    return lines


def build_export_table(
    doc_type: str,
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    *,
    schedule: Any | None = None,
    tech_spec: dict[str, Any] | None = None,
) -> tuple[ExportTableData | None, str | None, list[str]]:
    """Retorna (tabela, linha extra acima da tabela, linhas de corpo livre para esp. técnica)."""
    key = doc_type.strip().lower()
    if key in ("orc_sintetico", "orc_analitico"):
        return (
            build_orc_export_table(roots, meta, analitico=key == "orc_analitico"),
            None,
            [],
        )
    if key == "mcq":
        return build_mcq_export_table(roots), None, []
    if key == "cronograma":
        prazo, table = build_cronograma_export_table(roots, schedule)
        return table, prazo, []
    if key == "esp_tecnica":
        return None, None, build_esp_tecnica_body_lines(tech_spec)
    if key == "curva_abc":
        from pricing.budget.budget_analytics import build_curva_abc_export_table

        return build_curva_abc_export_table(roots), None, []
    if key == "curva_s":
        from pricing.budget.budget_analytics import build_curva_s_export_table
        from pricing.schedule.schedule_models import ProjectSchedule

        sched = schedule if isinstance(schedule, ProjectSchedule) else ProjectSchedule.from_dict(schedule)
        extra, table = build_curva_s_export_table(roots, sched)
        return table, extra, []
    if key == "histograma":
        from pricing.budget.budget_analytics import build_histograma_export_table
        from pricing.schedule.schedule_models import ProjectSchedule

        sched = schedule if isinstance(schedule, ProjectSchedule) else ProjectSchedule.from_dict(schedule)
        extra, table = build_histograma_export_table(roots, meta, sched)
        return table, extra, []
    raise ValueError(f"Tipo de documento inválido: {doc_type}")
