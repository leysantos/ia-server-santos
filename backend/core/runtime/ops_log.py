"""Ring buffer in-memory para log operacional ao vivo (Operations Console)."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OpsLogEntry:
    id: str
    ts: float
    source: str
    level: str
    message: str
    project_id: str | None = None
    job_id: str | None = None
    phase: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "source": self.source,
            "level": self.level,
            "message": self.message,
            "project_id": self.project_id,
            "job_id": self.job_id,
            "phase": self.phase,
            "meta": self.meta,
            "elapsed_sec": round(time.time() - self.ts, 1),
        }


class OpsLogBuffer:
    def __init__(self, max_size: int = 500) -> None:
        self._max = max_size
        self._lock = threading.Lock()
        self._entries: list[OpsLogEntry] = []

    def append(
        self,
        *,
        source: str,
        message: str,
        level: str = "info",
        project_id: str | None = None,
        job_id: str | None = None,
        phase: str | None = None,
        meta: dict | None = None,
    ) -> OpsLogEntry:
        entry = OpsLogEntry(
            id=uuid.uuid4().hex[:12],
            ts=time.time(),
            source=source,
            level=level,
            message=message.strip(),
            project_id=project_id,
            job_id=job_id,
            phase=phase,
            meta=meta or {},
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries = self._entries[-self._max :]
        return entry

    def list_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._entries[-limit:]
        return [e.to_dict() for e in reversed(rows)]


_buffer = OpsLogBuffer()


def append_ops_log(
    *,
    source: str,
    message: str,
    level: str = "info",
    project_id: str | None = None,
    job_id: str | None = None,
    phase: str | None = None,
    meta: dict | None = None,
) -> None:
    if not message.strip():
        return
    _buffer.append(
        source=source,
        message=message,
        level=level,
        project_id=project_id,
        job_id=job_id,
        phase=phase,
        meta=meta,
    )


def list_ops_logs(limit: int = 100) -> list[dict[str, Any]]:
    return _buffer.list_recent(limit=limit)
