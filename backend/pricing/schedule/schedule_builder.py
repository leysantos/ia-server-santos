"""Sincroniza cronograma a partir das linhas do orçamento."""

from __future__ import annotations

import math
import uuid
from typing import Any

from pricing.schedule.cpm_engine import run_cpm
from pricing.schedule.schedule_models import ProjectSchedule, ScheduleLink, ScheduleTask


def estimate_duration_days(quantity: float, unit: str) -> int:
    u = (unit or "").upper().replace("²", "2").replace("³", "3")
    qty = max(0.0, float(quantity or 0))

    if u in ("MES", "MÊS", "MÊS"):
        return max(1, int(math.ceil(qty * 30)) if qty else 30)
    if u == "H":
        return max(1, int(math.ceil(qty / 8)) if qty else 1)
    if u in ("M2", "M3", "M", "M3XKM", "TXKM", "KM"):
        return max(1, int(math.ceil(qty / 10)) if qty else 1)
    if u == "UN":
        return max(1, int(math.ceil(qty)) if qty else 1)
    if qty > 0:
        return max(1, int(math.ceil(qty)))
    return 1


def _is_service_row(row: dict[str, Any]) -> bool:
    return (
        row.get("row_type") == "S"
        and not row.get("is_memory_row")
    )


def _is_group_row(row: dict[str, Any]) -> bool:
    return row.get("row_type") in ("ETAPA", "SUB-ETAPA")


def sync_schedule_from_budget(
    rows: list[dict[str, Any]],
    existing: ProjectSchedule | None = None,
    project_start: str | None = None,
) -> ProjectSchedule:
    """Cria/atualiza tarefas a partir do orçamento; preserva duração e vínculos existentes."""
    schedule = existing or ProjectSchedule()
    if project_start:
        schedule.project_start = project_start

    old_by_row: dict[str, ScheduleTask] = {
        t.budget_row_id: t for t in schedule.tasks if t.budget_row_id and not t.is_summary
    }
    old_links = list(schedule.links)

    tasks: list[ScheduleTask] = []
    valid_row_ids: set[str] = set()

    for row in rows:
        if _is_group_row(row):
            tasks.append(
                ScheduleTask(
                    task_id=uuid.uuid4().hex[:12],
                    budget_row_id=str(row.get("row_id") or ""),
                    budget_code=str(row.get("code") or ""),
                    name=str(row.get("name") or ""),
                    row_type=str(row.get("row_type") or "ETAPA"),
                    parent_code=row.get("parent_code"),
                    duration_days=1,
                    is_summary=True,
                )
            )
        elif _is_service_row(row):
            row_id = str(row.get("row_id") or "")
            valid_row_ids.add(row_id)
            prev = old_by_row.get(row_id)
            duration = prev.duration_days if prev else estimate_duration_days(
                float(row.get("quantity") or 0),
                str(row.get("unit") or ""),
            )
            tasks.append(
                ScheduleTask(
                    task_id=prev.task_id if prev else uuid.uuid4().hex[:12],
                    budget_row_id=row_id,
                    budget_code=str(row.get("code") or ""),
                    name=str(row.get("name") or ""),
                    row_type="S",
                    parent_code=row.get("parent_code"),
                    duration_days=max(1, duration),
                    is_summary=False,
                    manual_start=prev.manual_start if prev else None,
                    early_start=prev.early_start if prev else None,
                    early_finish=prev.early_finish if prev else None,
                )
            )

    task_ids = {t.task_id for t in tasks if not t.is_summary}
    row_id_to_task = {t.budget_row_id: t.task_id for t in tasks if not t.is_summary}

    links: list[ScheduleLink] = []
    for link in old_links:
        if link.predecessor_id in task_ids and link.successor_id in task_ids:
            links.append(link)

    schedule.tasks = tasks
    schedule.links = links
    return run_cpm(schedule)


def update_task_duration(schedule: ProjectSchedule, task_id: str, duration_days: int) -> ProjectSchedule:
    task = schedule.task_by_id(task_id)
    if not task or task.is_summary:
        raise ValueError("Tarefa não encontrada ou é resumo")
    task.duration_days = max(1, int(duration_days))
    task.manual_start = None
    return run_cpm(schedule)


def update_project_start(schedule: ProjectSchedule, project_start: str) -> ProjectSchedule:
    schedule.project_start = project_start[:10]
    return run_cpm(schedule)


def add_link(
    schedule: ProjectSchedule,
    predecessor_id: str,
    successor_id: str,
    link_type: str = "FS",
    lag_days: int = 0,
) -> ProjectSchedule:
    if predecessor_id == successor_id:
        raise ValueError("Predecessora e sucessora devem ser diferentes")
    pred = schedule.task_by_id(predecessor_id)
    succ = schedule.task_by_id(successor_id)
    if not pred or not succ or pred.is_summary or succ.is_summary:
        raise ValueError("Tarefas inválidas para vínculo")

    for link in schedule.links:
        if link.predecessor_id == predecessor_id and link.successor_id == successor_id:
            raise ValueError("Vínculo já existe")

    schedule.links.append(
        ScheduleLink(
            link_id=uuid.uuid4().hex[:12],
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            link_type=link_type,  # type: ignore[arg-type]
            lag_days=max(0, int(lag_days)),
        )
    )
    return run_cpm(schedule)


def remove_link(schedule: ProjectSchedule, link_id: str) -> ProjectSchedule:
    schedule.links = [l for l in schedule.links if l.link_id != link_id]
    return run_cpm(schedule)
