"""CPM — caminho crítico (predecessoras FS/SS/FF/SF + folga)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask


class ScheduleCycleError(ValueError):
    pass


def _parse_iso(value: str) -> date:
    return date.fromisoformat(value[:10])


def _format_iso(d: date) -> str:
    return d.isoformat()


def _date_from_index(project_start: date, index: int) -> date:
    return project_start + timedelta(days=index)


def _day_index(project_start: date, target: date) -> int:
    return (target - project_start).days


def _topological_order(task_ids: list[str], links: list[tuple[str, str]]) -> list[str]:
    incoming: dict[str, set[str]] = {tid: set() for tid in task_ids}
    outgoing: dict[str, set[str]] = {tid: set() for tid in task_ids}
    for pred, succ in links:
        if pred not in incoming or succ not in incoming:
            continue
        incoming[succ].add(pred)
        outgoing[pred].add(succ)

    ready = [tid for tid in task_ids if not incoming[tid]]
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for succ in list(outgoing[node]):
            incoming[succ].discard(node)
            if not incoming[succ]:
                ready.append(succ)

    if len(order) != len(task_ids):
        raise ScheduleCycleError("Cronograma possui dependência circular")
    return order


def _constraint_es(
    pred_es: int,
    pred_ef: int,
    pred_dur: int,
    succ_dur: int,
    link_type: str,
    lag: int,
) -> int:
    if link_type == "FS":
        return pred_ef + 1 + lag
    if link_type == "SS":
        return pred_es + lag
    if link_type == "FF":
        return pred_ef + lag - succ_dur + 1
    if link_type == "SF":
        return pred_es + lag - succ_dur + 1
    return pred_ef + 1 + lag


def _constraint_lf(
    succ_ls: int,
    succ_lf: int,
    succ_dur: int,
    pred_dur: int,
    link_type: str,
    lag: int,
) -> int:
    if link_type == "FS":
        return succ_ls - lag - 1
    if link_type == "SS":
        return succ_ls + pred_dur - succ_dur - lag
    if link_type == "FF":
        return succ_lf - lag
    if link_type == "SF":
        return succ_lf + pred_dur - succ_dur - lag
    return succ_ls - lag - 1


def _forward_pass(
    tasks: dict[str, ScheduleTask],
    order: list[str],
    links: list[tuple[str, str, str, int]],
    project_start: date,
) -> tuple[dict[str, int], dict[str, int]]:
    es: dict[str, int] = {}
    ef: dict[str, int] = {}

    for tid in order:
        task = tasks[tid]
        duration = max(1, task.duration_days)
        preds = [(p, lt, lag) for p, s, lt, lag in links if s == tid]

        if preds:
            candidates = []
            for pred_id, link_type, lag in preds:
                if pred_id not in es:
                    continue
                candidates.append(
                    _constraint_es(
                        es[pred_id],
                        ef[pred_id],
                        max(1, tasks[pred_id].duration_days),
                        duration,
                        link_type,
                        lag,
                    )
                )
            es[tid] = max(candidates) if candidates else 0
        else:
            es[tid] = 0

        if task.manual_start:
            manual_idx = max(0, _day_index(project_start, _parse_iso(task.manual_start)))
            es[tid] = max(es[tid], manual_idx)

        ef[tid] = es[tid] + duration - 1

    return es, ef


def _backward_pass(
    tasks: dict[str, ScheduleTask],
    order: list[str],
    links: list[tuple[str, str, str, int]],
    project_end: int,
) -> tuple[dict[str, int], dict[str, int]]:
    ls: dict[str, int] = {}
    lf: dict[str, int] = {}

    for tid in reversed(order):
        task = tasks[tid]
        duration = max(1, task.duration_days)
        succs = [(s, lt, lag) for p, s, lt, lag in links if p == tid]

        if succs:
            candidates = []
            for succ_id, link_type, lag in succs:
                if succ_id not in ls:
                    continue
                candidates.append(
                    _constraint_lf(
                        ls[succ_id],
                        lf[succ_id],
                        max(1, tasks[succ_id].duration_days),
                        duration,
                        link_type,
                        lag,
                    )
                )
            lf[tid] = min(candidates) if candidates else project_end
        else:
            lf[tid] = project_end

        ls[tid] = lf[tid] - duration + 1

    return ls, lf


def _rollup_summaries(schedule: ProjectSchedule) -> None:
    leaves = [t for t in schedule.tasks if not t.is_summary and t.early_start]

    for task in schedule.tasks:
        if not task.is_summary:
            continue
        prefix = f"{task.budget_code}."
        desc = [
            d
            for d in leaves
            if d.budget_code == task.budget_code or d.budget_code.startswith(prefix)
        ]
        if not desc:
            task.early_start = None
            task.early_finish = None
            task.is_critical = False
            task.total_float_days = None
            continue
        starts = [_parse_iso(d.early_start) for d in desc if d.early_start]
        finishes = [_parse_iso(d.early_finish) for d in desc if d.early_finish]
        task.early_start = _format_iso(min(starts))
        task.early_finish = _format_iso(max(finishes))
        task.duration_days = max(1, (_parse_iso(task.early_finish) - _parse_iso(task.early_start)).days + 1)
        task.is_critical = any(d.is_critical for d in desc)
        floats = [d.total_float_days for d in desc if d.total_float_days is not None]
        task.total_float_days = min(floats) if floats else None


def run_cpm(schedule: ProjectSchedule) -> ProjectSchedule:
    project_start = _parse_iso(schedule.project_start)
    leaves = schedule.leaf_tasks()
    if not leaves:
        schedule.project_end = schedule.project_start
        schedule.calculated_at = datetime.now(timezone.utc).isoformat()
        return schedule

    task_map = {t.task_id: t for t in leaves}
    task_ids = list(task_map.keys())
    link_tuples: list[tuple[str, str, str, int]] = [
        (link.predecessor_id, link.successor_id, link.link_type, link.lag_days)
        for link in schedule.links
        if link.predecessor_id in task_map and link.successor_id in task_map
    ]

    order = _topological_order(task_ids, [(p, s) for p, s, _, _ in link_tuples])
    es, ef = _forward_pass(task_map, order, link_tuples, project_start)
    project_end = max(ef.values()) if ef else 0
    ls, lf = _backward_pass(task_map, order, link_tuples, project_end)

    for tid, task in task_map.items():
        task.early_start = _format_iso(_date_from_index(project_start, es[tid]))
        task.early_finish = _format_iso(_date_from_index(project_start, ef[tid]))
        task.late_start = _format_iso(_date_from_index(project_start, ls[tid]))
        task.late_finish = _format_iso(_date_from_index(project_start, lf[tid]))
        task.total_float_days = ls[tid] - es[tid]
        task.is_critical = task.total_float_days == 0

    schedule.project_end = _format_iso(_date_from_index(project_start, project_end))
    _rollup_summaries(schedule)
    schedule.calculated_at = datetime.now(timezone.utc).isoformat()
    return schedule
