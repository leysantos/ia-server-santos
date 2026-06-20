"""Testes CPM e sincronização de cronograma."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from pricing.schedule.cpm_engine import ScheduleCycleError, run_cpm
from pricing.schedule.schedule_builder import add_link, sync_schedule_from_budget
from pricing.schedule.schedule_models import ProjectSchedule, ScheduleLink, ScheduleTask


def _leaf(code: str, tid: str, dur: int) -> ScheduleTask:
    return ScheduleTask(
        task_id=tid,
        budget_row_id=tid,
        budget_code=code,
        name=f"Serviço {code}",
        duration_days=dur,
        is_summary=False,
    )


def test_cpm_linear_chain_critical():
    schedule = ProjectSchedule(project_start="2026-01-01")
    schedule.tasks = [_leaf("1.1", "a", 5), _leaf("1.2", "b", 3), _leaf("1.3", "c", 2)]
    schedule.links = [
        ScheduleLink("l1", "a", "b", "FS", 0),
        ScheduleLink("l2", "b", "c", "FS", 0),
    ]
    run_cpm(schedule)
    assert schedule.tasks[0].early_start == "2026-01-01"
    assert schedule.tasks[0].early_finish == "2026-01-05"
    assert schedule.tasks[1].early_start == "2026-01-06"
    assert schedule.tasks[2].early_finish == "2026-01-10"
    assert all(t.is_critical for t in schedule.tasks)
    assert schedule.project_end == "2026-01-10"


def test_cpm_parallel_one_critical_path():
    schedule = ProjectSchedule(project_start="2026-01-01")
    schedule.tasks = [_leaf("1.1", "a", 2), _leaf("1.2", "b", 5), _leaf("1.3", "c", 1)]
    schedule.links = [
        ScheduleLink("l1", "a", "c", "FS", 0),
        ScheduleLink("l2", "b", "c", "FS", 0),
    ]
    run_cpm(schedule)
    assert schedule.tasks[1].is_critical
    assert not schedule.tasks[0].is_critical
    assert schedule.tasks[2].early_start == "2026-01-06"


def test_cpm_detects_cycle():
    schedule = ProjectSchedule(project_start="2026-01-01")
    schedule.tasks = [_leaf("1.1", "a", 2), _leaf("1.2", "b", 2)]
    schedule.links = [
        ScheduleLink("l1", "a", "b", "FS", 0),
        ScheduleLink("l2", "b", "a", "FS", 0),
    ]
    with pytest.raises(ScheduleCycleError):
        run_cpm(schedule)


def test_sync_from_budget_rows():
    rows = [
        {"row_id": "e1", "code": "1", "name": "ETAPA A", "row_type": "ETAPA", "parent_code": None},
        {"row_id": "s1", "code": "1.1", "name": "Escavação", "row_type": "S", "parent_code": "1", "quantity": 10, "unit": "M3", "is_memory_row": False},
        {"row_id": "s2", "code": "1.2", "name": "Vigia", "row_type": "S", "parent_code": "1", "quantity": 6, "unit": "MES", "is_memory_row": False},
    ]
    schedule = sync_schedule_from_budget(rows)
    leaves = schedule.leaf_tasks()
    assert len(leaves) == 2
    assert leaves[0].duration_days >= 1
    assert leaves[1].duration_days == 180  # 6 meses × 30
    summaries = [t for t in schedule.tasks if t.is_summary]
    assert len(summaries) == 1


def test_add_link_recalculates():
    rows = [
        {"row_id": "s1", "code": "1.1", "name": "A", "row_type": "S", "parent_code": "1", "quantity": 1, "unit": "UN", "is_memory_row": False},
        {"row_id": "s2", "code": "1.2", "name": "B", "row_type": "S", "parent_code": "1", "quantity": 1, "unit": "UN", "is_memory_row": False},
    ]
    schedule = sync_schedule_from_budget(rows, project_start="2026-03-01")
    a, b = schedule.leaf_tasks()
    schedule = add_link(schedule, a.task_id, b.task_id, "FS", 0)
    assert b.early_start > a.early_finish or b.early_start == "2026-03-02"
