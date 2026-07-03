"""Montagem de seções de histograma (MO / equipamentos) a partir das CPUs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pricing.budget.budget_analytics import (
    HOURS_PER_WORKER_MONTH,
    _histogram_item_quantity,
    _item_cost_for_service,
    _overlap_days,
    _task_for_service,
    iter_service_items,
)
from pricing.budget.budget_export_tables import (
    _fetch_open_composition_items,
    _resolve_open_composition_lookup,
)
from pricing.budget.budget_resource_classification import (
    is_histogram_direct_labor,
    resolve_resource_category,
)
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_curves import _days_between, build_schedule_curves_by_month
from pricing.schedule.schedule_models import ProjectSchedule

HistogramCategory = Literal["mao_obra", "equipamento"]

SECTION_TITLES: dict[HistogramCategory, str] = {
    "mao_obra": "HISTOGRAMA DE MÃO DE OBRA DIRETA",
    "equipamento": "HISTOGRAMA DE EQUIPAMENTOS",
}


@dataclass
class HistogramItemRow:
    index: int
    code: str
    description: str
    unit: str
    values: list[float] = field(default_factory=list)
    values_money: list[float] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(self.values)

    @property
    def total_money(self) -> float:
        return sum(self.values_money)


@dataclass
class HistogramSection:
    title: str
    category: HistogramCategory
    period_labels: list[int]
    month_labels: list[str]
    items: list[HistogramItemRow] = field(default_factory=list)
    monthly_totals: list[float] = field(default_factory=list)
    monthly_totals_money: list[float] = field(default_factory=list)

    @property
    def period_count(self) -> int:
        return len(self.period_labels)


@dataclass
class HistogramReport:
    empresa: str
    cliente: str
    obra: str
    mao_obra: HistogramSection | None
    equipamento: HistogramSection | None
    services_with_cpu: int = 0


def _item_key(item: dict[str, Any]) -> str:
    return f"{item.get('code')}|{item.get('description')}|{item.get('unit')}"


def build_histogram_section(
    category: HistogramCategory,
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
    *,
    price_mode: str = "comd",
) -> HistogramSection | None:
    if not schedule or not schedule.project_start:
        return None

    from pricing.budget.budget_analytics import flatten_budget_items

    schedule_months, _, _ = build_schedule_curves_by_month(schedule, flatten_budget_items(roots))
    if not schedule_months:
        return None

    period_labels = [
        _days_between(schedule.project_start, m.month_end_iso) + 1 for m in schedule_months
    ]
    month_labels = [m.label for m in schedule_months]
    month_count = len(schedule_months)

    comp_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    accum: dict[str, dict[str, Any]] = {}
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
        task = _task_for_service(schedule, service.row_id)

        for item in items:
            if resolve_resource_category(item) != category:
                continue
            if category == "mao_obra" and not is_histogram_direct_labor(item):
                continue

            qty_base = _histogram_item_quantity(item, service_qty, category)
            val_base = _item_cost_for_service(item, service_qty, price_mode)  # type: ignore[arg-type]
            if qty_base <= 0 and val_base <= 0:
                continue

            key = _item_key(item)
            row = accum.get(key)
            if not row:
                row = {
                    "code": str(item.get("code") or ""),
                    "description": str(item.get("description") or "").strip(),
                    "unit": str(item.get("unit") or ""),
                    "monthly_qty": [0.0] * month_count,
                    "monthly_val": [0.0] * month_count,
                }
                accum[key] = row

            if not task or not task.early_start or not task.early_finish:
                row["monthly_qty"][0] += qty_base
                row["monthly_val"][0] += val_base
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
                row["monthly_qty"][i] += qty_base * factor
                row["monthly_val"][i] += val_base * factor

    item_rows: list[HistogramItemRow] = []
    for data in accum.values():
        total_q = sum(data["monthly_qty"])
        if total_q <= 0.0001 and sum(data["monthly_val"]) <= 0.0001:
            continue
        item_rows.append(
            HistogramItemRow(
                index=0,
                code=data["code"],
                description=data["description"],
                unit=data["unit"],
                values=[round(v, 2) for v in data["monthly_qty"]],
                values_money=[round(v, 2) for v in data["monthly_val"]],
            )
        )

    item_rows.sort(key=lambda r: r.total, reverse=True)
    for i, row in enumerate(item_rows, start=1):
        row.index = i

    if not item_rows:
        return None

    monthly_totals = [
        round(sum(row.values[i] for row in item_rows), 2) for i in range(month_count)
    ]
    monthly_totals_money = [
        round(sum(row.values_money[i] for row in item_rows), 2) for i in range(month_count)
    ]

    return HistogramSection(
        title=SECTION_TITLES[category],
        category=category,
        period_labels=period_labels,
        month_labels=month_labels,
        items=item_rows,
        monthly_totals=monthly_totals,
        monthly_totals_money=monthly_totals_money,
    )


def build_histogram_report(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
    *,
    price_mode: str | None = None,
) -> HistogramReport:
    from pricing.budget.budget_export_tables import budget_desoneracao_mode

    mode = price_mode or budget_desoneracao_mode(roots)
    mo = build_histogram_section("mao_obra", roots, meta, schedule, price_mode=mode)
    eq = build_histogram_section("equipamento", roots, meta, schedule, price_mode=mode)
    svc = max(
        (mo and len(mo.items)) or 0,
        (eq and len(eq.items)) or 0,
    )
    return HistogramReport(
        empresa=meta.empresa or meta.orgao or "",
        cliente=meta.orgao or meta.empresa or "",
        obra=meta.projeto or meta.objeto or "",
        mao_obra=mo,
        equipamento=eq,
        services_with_cpu=svc,
    )
