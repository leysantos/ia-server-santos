"""Modelo de cronograma — tarefas ligadas ao orçamento (S1 manual + CPM)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal

LinkType = Literal["FS", "SS", "FF", "SF"]


def _today_iso() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ScheduleLink:
    link_id: str
    predecessor_id: str
    successor_id: str
    link_type: LinkType = "FS"
    lag_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "predecessor_id": self.predecessor_id,
            "successor_id": self.successor_id,
            "link_type": self.link_type,
            "lag_days": self.lag_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleLink:
        return cls(
            link_id=str(data.get("link_id") or uuid.uuid4().hex[:12]),
            predecessor_id=str(data["predecessor_id"]),
            successor_id=str(data["successor_id"]),
            link_type=str(data.get("link_type") or "FS"),  # type: ignore[arg-type]
            lag_days=int(data.get("lag_days") or 0),
        )


@dataclass
class ScheduleTask:
    task_id: str
    budget_row_id: str
    budget_code: str
    name: str
    row_type: str = "S"
    parent_code: str | None = None
    duration_days: int = 1
    is_summary: bool = False
    manual_start: str | None = None
    early_start: str | None = None
    early_finish: str | None = None
    late_start: str | None = None
    late_finish: str | None = None
    total_float_days: int | None = None
    is_critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "budget_row_id": self.budget_row_id,
            "budget_code": self.budget_code,
            "name": self.name,
            "row_type": self.row_type,
            "parent_code": self.parent_code,
            "duration_days": self.duration_days,
            "is_summary": self.is_summary,
            "manual_start": self.manual_start,
            "early_start": self.early_start,
            "early_finish": self.early_finish,
            "late_start": self.late_start,
            "late_finish": self.late_finish,
            "total_float_days": self.total_float_days,
            "is_critical": self.is_critical,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleTask:
        return cls(
            task_id=str(data.get("task_id") or uuid.uuid4().hex[:12]),
            budget_row_id=str(data.get("budget_row_id") or ""),
            budget_code=str(data.get("budget_code") or ""),
            name=str(data.get("name") or ""),
            row_type=str(data.get("row_type") or "S"),
            parent_code=data.get("parent_code"),
            duration_days=max(1, int(data.get("duration_days") or 1)),
            is_summary=bool(data.get("is_summary")),
            manual_start=data.get("manual_start"),
            early_start=data.get("early_start"),
            early_finish=data.get("early_finish"),
            late_start=data.get("late_start"),
            late_finish=data.get("late_finish"),
            total_float_days=data.get("total_float_days"),
            is_critical=bool(data.get("is_critical")),
        )


@dataclass
class ProjectSchedule:
    project_start: str = field(default_factory=_today_iso)
    project_end: str | None = None
    tasks: list[ScheduleTask] = field(default_factory=list)
    links: list[ScheduleLink] = field(default_factory=list)
    calculated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_start": self.project_start,
            "project_end": self.project_end,
            "tasks": [t.to_dict() for t in self.tasks],
            "links": [l.to_dict() for l in self.links],
            "calculated_at": self.calculated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ProjectSchedule | None:
        if not data:
            return None
        return cls(
            project_start=str(data.get("project_start") or _today_iso()),
            project_end=data.get("project_end"),
            tasks=[ScheduleTask.from_dict(t) for t in data.get("tasks") or []],
            links=[ScheduleLink.from_dict(l) for l in data.get("links") or []],
            calculated_at=data.get("calculated_at"),
        )

    def task_by_id(self, task_id: str) -> ScheduleTask | None:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

    def leaf_tasks(self) -> list[ScheduleTask]:
        return [t for t in self.tasks if not t.is_summary]
