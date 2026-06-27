"""Curva ABC, Curva S e Histograma — cálculo e tabelas de exportação."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pricing.budget.budget_export_tables import (
    ExportTableData,
    _cell_money,
    _fetch_open_composition_items,
    _resolve_open_composition_lookup,
    budget_desoneracao_mode,
)
from pricing.budget.ppd_layout import ROW_TYPE_SERVICO
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_curves import (
    _days_between,
    build_schedule_curves_by_month,
)
from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask

ResourceCategory = Literal["equipamento", "insumo", "mao_obra"]
PriceMode = Literal["comd", "semd"]
AbcClass = Literal["A", "B", "C"]


@dataclass
class AbcItem:
    row_id: str
    code: str
    name: str
    value: float
    pct: float
    cumulative_pct: float
    abc_class: AbcClass


@dataclass
class StackedHistogramMonth:
    month_index: int
    label: str
    period_day: int
    equipamento: float
    insumo: float
    mao_obra: float
    total: float
    total_with_bdi: float


def _is_service_item(item: BudgetItem) -> bool:
    return (
        item.row_type in (ROW_TYPE_SERVICO, "SERVICO")
        or item.item_type == BudgetItemType.COMPOSITION
    ) and item.row_type not in ("ETAPA", "SUB-ETAPA")


def iter_service_items(roots: list[BudgetItem]) -> list[BudgetItem]:
    out: list[BudgetItem] = []

    def walk(node: BudgetItem) -> None:
        if node.metadata.get("is_memory_row") or node.row_type == "MEMORIA":
            return
        if _is_service_item(node):
            out.append(node)
        for child in node.children:
            walk(child)

    for root in roots:
        walk(root)
    return out


def flatten_budget_items(roots: list[BudgetItem]) -> list[BudgetItem]:
    """Lista plana de todos os itens (para lookup por row_id)."""
    rows: list[BudgetItem] = []

    def walk(node: BudgetItem) -> None:
        rows.append(node)
        for child in node.children:
            if child.metadata.get("is_memory_row") or child.row_type == "MEMORIA":
                continue
            walk(child)

    for root in roots:
        walk(root)
    return rows


def _service_value(item: BudgetItem) -> float:
    return max(0.0, item.effective_total())


def _classify_abc(cumulative_pct: float) -> AbcClass:
    if cumulative_pct <= 80:
        return "A"
    if cumulative_pct <= 95:
        return "B"
    return "C"


def build_abc_curve(roots: list[BudgetItem]) -> list[AbcItem]:
    services = iter_service_items(roots)
    sorted_items = sorted(services, key=lambda r: _service_value(r), reverse=True)
    total = sum(_service_value(r) for r in sorted_items) or 1.0
    cumulative = 0.0
    result: list[AbcItem] = []
    for row in sorted_items:
        value = _service_value(row)
        pct = (value / total) * 100
        cumulative += pct
        result.append(
            AbcItem(
                row_id=row.row_id,
                code=str(row.code or ""),
                name=str(row.name or ""),
                value=value,
                pct=pct,
                cumulative_pct=cumulative,
                abc_class=_classify_abc(cumulative),
            )
        )
    return result


def _task_for_service(schedule: ProjectSchedule, row_id: str) -> ScheduleTask | None:
    for task in schedule.tasks:
        if (
            task.budget_row_id == row_id
            and not task.is_summary
            and task.early_start
            and task.early_finish
        ):
            return task
    return None


def _normalize_resource_category(item_type: str) -> ResourceCategory | None:
    key = item_type.lower().replace(" ", "_")
    if key == "equipamento":
        return "equipamento"
    if key in ("insumo", "material"):
        return "insumo"
    if key in ("mao_obra", "maodeobra"):
        return "mao_obra"
    return None


def _item_cost_for_service(
    cpu_item: dict[str, Any],
    service_qty: float,
    mode: PriceMode,
) -> float:
    if mode == "semd":
        unit_partial = cpu_item.get("partial_cost_sem")
        if unit_partial is None:
            unit_partial = cpu_item.get("partial_cost")
    else:
        unit_partial = cpu_item.get("partial_cost")
    return max(0.0, float(unit_partial or 0) * max(0.0, service_qty))


def _category_totals_from_composition(
    items: list[dict[str, Any]],
    service_qty: float,
    mode: PriceMode,
) -> dict[ResourceCategory, float]:
    totals: dict[ResourceCategory, float] = {
        "equipamento": 0.0,
        "insumo": 0.0,
        "mao_obra": 0.0,
    }
    composicao_cost = 0.0
    for item in items:
        cat = _normalize_resource_category(str(item.get("item_type") or ""))
        cost = _item_cost_for_service(item, service_qty, mode)
        if cat:
            totals[cat] += cost
        elif str(item.get("item_type") or "").lower() == "composicao":
            composicao_cost += cost
    direct_sum = totals["equipamento"] + totals["insumo"] + totals["mao_obra"]
    if composicao_cost > 0 and direct_sum > 0:
        for cat in ("equipamento", "insumo", "mao_obra"):
            totals[cat] += composicao_cost * (totals[cat] / direct_sum)
    elif composicao_cost > 0:
        totals["insumo"] += composicao_cost
    return totals


def _service_bdi_factor(item: BudgetItem, analytical_cost: float) -> float:
    effective = _service_value(item)
    if analytical_cost > 0:
        return effective / analytical_cost
    unit_base = max(0.0, float(item.unit_cost or 0) * max(0.0, float(item.quantity or 0)))
    return effective / unit_base if unit_base > 0 else 1.0


def _overlap_days(
    range_start: str,
    range_end: str,
    period_start: str,
    period_end: str,
) -> int:
    from datetime import date

    def parse(iso: str) -> date:
        y, m, d = iso[:10].split("-")
        return date(int(y), int(m), int(d))

    rs = parse(range_start)
    re = parse(range_end)
    ps = parse(period_start)
    pe = parse(period_end)
    start = max(rs, ps)
    end = min(re, pe)
    if end < start:
        return 0
    return (end - start).days + 1


def build_stacked_histogram(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
    *,
    price_mode: PriceMode | None = None,
) -> tuple[list[StackedHistogramMonth], float, float, float, float, float]:
    """Retorna meses, totais EQ/INS/MO/total/totalWithBdi, services_with_cpu."""
    if not schedule or not schedule.project_start:
        return [], 0.0, 0.0, 0.0, 0.0, 0.0

    mode: PriceMode = price_mode or budget_desoneracao_mode(roots)  # type: ignore[assignment]
    schedule_months, _, _ = build_schedule_curves_by_month(schedule, flatten_budget_items(roots))
    if not schedule_months:
        return [], 0.0, 0.0, 0.0, 0.0, 0.0

    project_start = schedule.project_start
    buckets: list[dict[str, float]] = [
        {
            "equipamento": 0.0,
            "insumo": 0.0,
            "mao_obra": 0.0,
            "total": 0.0,
            "total_with_bdi": 0.0,
        }
        for _ in schedule_months
    ]

    comp_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    services_with_cpu = 0

    for service in iter_service_items(roots):
        lookup = _resolve_open_composition_lookup(service, meta)
        if not lookup or not service.source_code:
            continue
        items = _fetch_open_composition_items(service.source_code, lookup, comp_cache)
        if not items:
            continue
        services_with_cpu += 1

        service_qty = float(service.quantity or 1)
        category_totals = _category_totals_from_composition(items, service_qty, mode)
        category_sum = sum(category_totals.values())
        if category_sum <= 0:
            continue
        bdi_factor = _service_bdi_factor(service, category_sum)
        task = _task_for_service(schedule, service.row_id)

        if not task or not task.early_start or not task.early_finish:
            b = buckets[0]
            b["equipamento"] += category_totals["equipamento"]
            b["insumo"] += category_totals["insumo"]
            b["mao_obra"] += category_totals["mao_obra"]
            b["total"] += category_sum
            b["total_with_bdi"] += category_sum * bdi_factor
            continue

        duration = max(1, task.duration_days)
        for i, m in enumerate(schedule_months):
            overlap = _overlap_days(
                task.early_start,
                task.early_finish,
                m.month_start_iso,
                m.month_end_iso,
            )
            if overlap <= 0:
                continue
            factor = overlap / duration
            b = buckets[i]
            b["equipamento"] += category_totals["equipamento"] * factor
            b["insumo"] += category_totals["insumo"] * factor
            b["mao_obra"] += category_totals["mao_obra"] * factor
            b["total"] += category_sum * factor
            b["total_with_bdi"] += category_sum * factor * bdi_factor

    months: list[StackedHistogramMonth] = []
    for i, m in enumerate(schedule_months):
        period_day = _days_between(project_start, m.month_end_iso) + 1
        b = buckets[i]
        months.append(
            StackedHistogramMonth(
                month_index=i,
                label=m.label,
                period_day=period_day,
                equipamento=b["equipamento"],
                insumo=b["insumo"],
                mao_obra=b["mao_obra"],
                total=b["total"],
                total_with_bdi=b["total_with_bdi"],
            )
        )

    totals_eq = sum(m.equipamento for m in months)
    totals_ins = sum(m.insumo for m in months)
    totals_mo = sum(m.mao_obra for m in months)
    totals_all = sum(m.total for m in months)
    totals_bdi = sum(m.total_with_bdi for m in months)
    return months, totals_eq, totals_ins, totals_mo, totals_all, totals_bdi


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def build_curva_abc_export_table(roots: list[BudgetItem]) -> ExportTableData:
    items = build_abc_curve(roots)
    headers = ["Item", "Código", "Descrição", "Valor (R$)", "% Individual", "% Acumulado", "Classe"]
    rows: list[list[Any]] = []
    bold_rows: set[int] = set()

    for idx, item in enumerate(items):
        if item.abc_class == "A":
            bold_rows.add(idx)
        rows.append([
            str(idx + 1),
            item.code,
            item.name,
            _cell_money(item.value),
            _fmt_pct(item.pct),
            _fmt_pct(item.cumulative_pct),
            item.abc_class,
        ])

    total = sum(i.value for i in items)
    summary: list[Any] = ["", "", "TOTAL", _cell_money(total), "100,00", "100,00", ""]
    rows.append(summary)
    bold_rows.add(len(rows) - 1)

    return ExportTableData(
        headers=headers,
        rows=rows,
        right_cols=(3, 4, 5),
        summary_rows=1,
        bold_rows=bold_rows,
    )


def build_curva_s_export_table(
    roots: list[BudgetItem],
    schedule: ProjectSchedule | None,
) -> tuple[str | None, ExportTableData]:
    if not schedule or not schedule.project_start:
        raise ValueError("Cronograma não sincronizado — sincronize na aba Cronograma antes de exportar.")

    flat = flatten_budget_items(roots)
    months, total_financial, _ = build_schedule_curves_by_month(schedule, flat)
    if not months:
        raise ValueError("Cronograma sem meses válidos.")

    fin_denom = total_financial if total_financial > 0 else 1.0
    headers = [
        "Mês",
        "Dia acum.",
        "Físico mensal (%)",
        "Físico acum. (%)",
        "Financeiro mensal (R$)",
        "Financeiro acum. (R$)",
        "Financeiro acum. (%)",
    ]
    rows: list[list[Any]] = []
    project_start = schedule.project_start

    for m in months:
        period_day = _days_between(project_start, m.month_end_iso) + 1
        fin_cum_pct = (m.financial_cumulative / fin_denom) * 100
        rows.append([
            m.label,
            period_day,
            _fmt_pct(m.physical_monthly_pct),
            _fmt_pct(m.physical_cumulative_pct),
            _cell_money(m.financial_monthly),
            _cell_money(m.financial_cumulative),
            _fmt_pct(fin_cum_pct),
        ])

    extra = f"Valor total do orçamento: {_cell_money(total_financial)}"
    return extra, ExportTableData(
        headers=headers,
        rows=rows,
        right_cols=(1, 2, 3, 4, 5, 6),
    )


def build_histograma_export_table(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
) -> tuple[str | None, ExportTableData]:
    months, _, _, _, total_cpu, total_bdi = build_stacked_histogram(
        roots, meta, schedule
    )
    if not months:
        raise ValueError(
            "Histograma indisponível — sincronize o cronograma e verifique CPUs dos serviços."
        )

    mode = budget_desoneracao_mode(roots)
    mode_label = "Com desoneração" if mode == "comd" else "Sem desoneração"
    headers = [
        "Mês",
        "Dia acum.",
        "Insumos (R$)",
        "Equipamentos (R$)",
        "Mão de obra (R$)",
        "Total CPU (R$)",
        "Ref. com BDI (R$)",
    ]
    rows: list[list[Any]] = []
    for m in months:
        rows.append([
            m.label,
            m.period_day,
            _cell_money(m.insumo),
            _cell_money(m.equipamento),
            _cell_money(m.mao_obra),
            _cell_money(m.total),
            _cell_money(m.total_with_bdi),
        ])

    rows.append([
        "TOTAL",
        "",
        _cell_money(sum(m.insumo for m in months)),
        _cell_money(sum(m.equipamento for m in months)),
        _cell_money(sum(m.mao_obra for m in months)),
        _cell_money(total_cpu),
        _cell_money(total_bdi),
    ])

    extra = f"Preços: {mode_label} · Serviços com CPU rateados pelo cronograma"
    return extra, ExportTableData(
        headers=headers,
        rows=rows,
        right_cols=(1, 2, 3, 4, 5, 6),
        summary_rows=1,
        bold_rows={len(rows) - 1},
    )
