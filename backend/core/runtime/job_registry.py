"""Registro in-memory de jobs longos da aplicação (visão, orçamento, etc.)."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeJob:
    id: str
    kind: str
    label: str
    project_id: str | None = None
    model: str | None = None
    phase: str | None = None
    message: str | None = None
    percent: int | None = None
    current: int | None = None
    total: int | None = None
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancel_requested: bool = False
    status: str = "running"  # running | completed | cancelled | error
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "project_id": self.project_id,
            "model": self.model,
            "phase": self.phase,
            "message": self.message,
            "percent": self.percent,
            "current": self.current,
            "total": self.total,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "cancel_requested": self.cancel_requested,
            "status": self.status,
            "meta": self.meta,
            "elapsed_sec": round(time.time() - self.started_at, 1),
        }


class JobRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, RuntimeJob] = {}

    def register(
        self,
        *,
        kind: str,
        label: str,
        project_id: str | None = None,
        model: str | None = None,
        meta: dict | None = None,
        job_id: str | None = None,
    ) -> RuntimeJob:
        job = RuntimeJob(
            id=job_id or uuid.uuid4().hex,
            kind=kind,
            label=label,
            project_id=project_id,
            model=model,
            meta=meta or {},
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def update(self, job_id: str, **fields: Any) -> RuntimeJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in fields.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()
            return job

    def request_cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != "running":
                return False
            job.cancel_requested = True
            job.updated_at = time.time()
            return True

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.cancel_requested)

    def finish(self, job_id: str, *, status: str = "completed", message: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = status
            if message:
                job.message = message
            job.updated_at = time.time()

    def get(self, job_id: str) -> RuntimeJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, *, active_only: bool = False, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._jobs.values())
        rows.sort(key=lambda j: j.updated_at, reverse=True)
        if active_only:
            rows = [j for j in rows if j.status == "running"]
        return [j.to_dict() for j in rows[:limit]]

    def prune_old(self, max_age_sec: float = 3600) -> int:
        """Remove jobs concluídos há mais de max_age_sec."""
        now = time.time()
        removed = 0
        with self._lock:
            stale = [
                jid
                for jid, job in self._jobs.items()
                if job.status != "running" and (now - job.updated_at) > max_age_sec
            ]
            for jid in stale:
                del self._jobs[jid]
                removed += 1
        return removed

    def has_active_kind(self, kinds: str | tuple[str, ...]) -> bool:
        wanted = (kinds,) if isinstance(kinds, str) else tuple(kinds)
        with self._lock:
            return any(job.status == "running" and job.kind in wanted for job in self._jobs.values())


_registry = JobRegistry()


def get_job_registry() -> JobRegistry:
    return _registry
