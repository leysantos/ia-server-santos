"""Curvas físico-financeiras mensais — espelho de frontend/lib/schedule-curves.ts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pricing.models.budget_item import BudgetItem
    from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask


@dataclass
class MonthBucket:
    month_index: int
    label: str
    month_start_iso: str
    month_end_iso: str
    physical_monthly_pct: float
    physical_cumulative_pct: float
    financial_monthly: float
    financial_cumulative: float


def _parse_date(iso: str) -> date:
    y, m, d = iso[:10].split("-")
    return date(int(y), int(m), int(d))


def _days_between(start: str, end: str) -> int:
    a = _parse_date(start)
    b = _parse_date(end)
    return (b - a).days


def _add_days(iso: str, days: int) -> str:
    d = _parse_date(iso) + timedelta(days=days)
    return d.isoformat()[:10]


def _overlap_days(range_start: str, range_end: str, period_start: str, period_end: str) -> int:
    rs = _parse_date(range_start)
    re = _parse_date(range_end)
    ps = _parse_date(period_start)
    pe = _parse_date(period_end)
    start = max(rs, ps)
    end = min(re, pe)
    if end < start:
        return 0
    return (end - start).days + 1


def _month_start_date(project_start: str, month_index: int) -> date:
    s = _parse_date(project_start)
    month = s.month - 1 + month_index
    year = s.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def _month_end_date(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1) - timedelta(days=1)
    return date(d.year, d.month + 1, 1) - timedelta(days=1)


def _format_iso(d: date) -> str:
    return d.isoformat()[:10]


def count_months(project_start: str, project_end: str) -> int:
    s = _parse_date(project_start)
    e = _parse_date(project_end)
    return max(1, (e.year - s.year) * 12 + (e.month - s.month) + 1)


def month_label(d: date) -> str:
    months = ("jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez.")
    return f"{months[d.month - 1]} de {d.year % 100:02d}"


def _clip_to_project(
    period_start: str,
    period_end: str,
    project_start: str,
    project_end: str,
) -> tuple[str, str] | None:
    end = project_end or project_start
    start = period_start if period_start >= project_start else project_start
    finish = period_end if period_end <= end else end
    if start > finish:
        return None
    return start, finish


def _row_for_task(rows: list[BudgetItem], task: ScheduleTask) -> BudgetItem | None:
    for row in rows:
        if row.row_id == task.budget_row_id:
            return row
    return None


def _leaf_task_for_service(schedule: ProjectSchedule, row_id: str) -> ScheduleTask | None:
    for task in schedule.tasks:
        if (
            task.budget_row_id == row_id
            and not task.is_summary
            and task.early_start
            and task.early_finish
        ):
            return task
    return None


def unscheduled_service_items(
    schedule: ProjectSchedule,
    items: list[BudgetItem],
) -> list[BudgetItem]:
    from pricing.budget.ppd_layout import ROW_TYPE_SERVICO

    return [
        item
        for item in items
        if item.row_type == ROW_TYPE_SERVICO
        and not item.metadata.get("is_memory_row")
        and not _leaf_task_for_service(schedule, item.row_id)
    ]


def _service_physical_weight(item: BudgetItem) -> float:
    qty = max(0.0, float(item.quantity or 0))
    return qty if qty > 0 else 1.0


def _service_financial_cost(item: BudgetItem) -> float:
    return float(item.effective_total())


def _leaf_tasks_for_curve(
    schedule: ProjectSchedule,
    visible_tasks: list[ScheduleTask] | None = None,
) -> list[ScheduleTask]:
    all_leaves = [
        t for t in schedule.tasks if not t.is_summary and t.early_start and t.early_finish
    ]
    if not visible_tasks:
        return all_leaves

    etapa_only = all(t.is_summary and t.row_type == "ETAPA" for t in visible_tasks)
    if not etapa_only:
        ids = {t.task_id for t in visible_tasks}
        return [t for t in all_leaves if t.task_id in ids]

    result: list[ScheduleTask] = []
    for etapa in visible_tasks:
        if not (etapa.early_start and etapa.early_finish):
            continue
        dur = max(1, _days_between(etapa.early_start, etapa.early_finish) + 1)
        result.append(
            ScheduleTask(
                task_id=etapa.task_id,
                budget_row_id=etapa.budget_row_id,
                budget_code=etapa.budget_code,
                name=etapa.name,
                row_type=etapa.row_type,
                parent_code=etapa.parent_code,
                duration_days=dur,
                is_summary=etapa.is_summary,
                manual_start=etapa.manual_start,
                early_start=etapa.early_start,
                early_finish=etapa.early_finish,
                late_start=etapa.late_start,
                late_finish=etapa.late_finish,
                total_float_days=etapa.total_float_days,
                is_critical=etapa.is_critical,
            )
        )
    return result


def _weight_and_cost(
    task: ScheduleTask,
    rows: list[BudgetItem],
) -> tuple[float, float]:
    from pricing.budget.ppd_layout import ROW_TYPE_SERVICO

    if task.is_summary:
        prefix = f"{task.budget_code}."
        children = [
            r
            for r in rows
            if r.row_type == ROW_TYPE_SERVICO
            and not r.metadata.get("is_memory_row")
            and (r.code == task.budget_code or str(r.code).startswith(prefix))
        ]
        weight = 0.0
        cost = 0.0
        for row in children:
            qty = max(0.0, float(row.quantity or 0))
            weight += qty if qty > 0 else 1.0
            cost += _service_financial_cost(row)
        if weight <= 0:
            weight = float(len(children) or 1)
        return weight, cost

    row = _row_for_task(rows, task)
    qty = max(0.0, float(row.quantity or 0)) if row else 0.0
    weight = qty if qty > 0 else 1.0
    cost = _service_financial_cost(row) if row else 0.0
    return weight, cost


def build_schedule_curves_by_month(
    schedule: ProjectSchedule,
    rows: list[BudgetItem],
    visible_tasks: list[ScheduleTask] | None = None,
) -> tuple[list[MonthBucket], float, float]:
    project_start = schedule.project_start
    project_end = schedule.project_end or project_start
    month_count = count_months(project_start, project_end)
    leaves = _leaf_tasks_for_curve(schedule, visible_tasks)

    total_physical_weight = 0.0
    total_financial = 0.0

    for task in leaves:
        weight, cost = _weight_and_cost(task, rows)
        total_physical_weight += weight
        total_financial += cost

    orphans = unscheduled_service_items(schedule, rows)
    orphan_weight = 0.0
    orphan_cost = 0.0
    for row in orphans:
        orphan_weight += _service_physical_weight(row)
        orphan_cost += _service_financial_cost(row)
    total_physical_weight += orphan_weight
    total_financial += orphan_cost

    if total_physical_weight <= 0:
        total_physical_weight = float(len(leaves) or len(orphans) or 1)

    months: list[MonthBucket] = []
    physical_cum = 0.0
    financial_cum = 0.0
    orphans_allocated = False

    for m in range(month_count):
        m_start = _month_start_date(project_start, m)
        m_end = _month_end_date(m_start)
        period_start = _format_iso(m_start)
        period_end = _format_iso(m_end)
        clip = _clip_to_project(period_start, period_end, project_start, project_end)
        if not clip:
            continue

        physical_month = 0.0
        financial_month = 0.0

        for task in leaves:
            weight, cost = _weight_and_cost(task, rows)
            dur = max(1, task.duration_days)
            overlap = _overlap_days(
                task.early_start or period_start,
                task.early_finish or period_end,
                clip[0],
                clip[1],
            )
            if overlap <= 0:
                continue
            physical_month += (weight * overlap) / dur
            financial_month += (cost * overlap) / dur

        if not orphans_allocated and (orphan_weight > 0 or orphan_cost > 0):
            physical_month += orphan_weight
            financial_month += orphan_cost
            orphans_allocated = True

        physical_monthly_pct = (physical_month / total_physical_weight) * 100
        physical_cum = min(100.0, physical_cum + physical_monthly_pct)
        financial_cum += financial_month

        months.append(
            MonthBucket(
                month_index=len(months),
                label=month_label(m_start),
                month_start_iso=period_start,
                month_end_iso=period_end,
                physical_monthly_pct=physical_monthly_pct,
                physical_cumulative_pct=physical_cum,
                financial_monthly=financial_month,
                financial_cumulative=financial_cum,
            )
        )

    return months, total_financial, total_physical_weight
