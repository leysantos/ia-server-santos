"""Event bus in-process — persiste eventos em PostgreSQL."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Any, Callable

from sqlalchemy.orm import Session

from core.database.workflow_models import WorkflowEvent
from core.workflow.events.types import WorkflowEventType

logger = logging.getLogger(__name__)

EventHandler = Callable[[WorkflowEventType, dict[str, Any], Session | None], None]


class WorkflowEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: WorkflowEventType | str, handler: EventHandler) -> None:
        self._handlers[str(event_type)].append(handler)

    def publish(
        self,
        event_type: WorkflowEventType | str,
        payload: dict[str, Any] | None = None,
        *,
        project_id: str | uuid.UUID | None = None,
        company_id: str | uuid.UUID | None = None,
        actor: str | None = None,
        db: Session | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        payload = dict(payload or {})
        payload.setdefault("event_type", str(event_type))

        event_record: dict[str, Any] | None = None
        if persist and db is not None:
            event_record = self._persist(
                db,
                str(event_type),
                payload,
                project_id=project_id,
                company_id=company_id,
                actor=actor,
            )

        for handler in self._handlers.get(str(event_type), []):
            try:
                handler(event_type, payload, db)
            except Exception as exc:
                logger.warning("workflow handler %s failed: %s", handler, exc)

        for handler in self._handlers.get("*", []):
            try:
                handler(event_type, payload, db)
            except Exception as exc:
                logger.warning("workflow wildcard handler failed: %s", exc)

        return event_record or {"event_type": str(event_type), "payload": payload, "persisted": False}

    @staticmethod
    def _persist(
        db: Session,
        event_type: str,
        payload: dict[str, Any],
        *,
        project_id: str | uuid.UUID | None,
        company_id: str | uuid.UUID | None,
        actor: str | None,
    ) -> dict[str, Any]:
        pid = uuid.UUID(str(project_id)) if project_id else None
        cid = uuid.UUID(str(company_id)) if company_id else None
        row = WorkflowEvent(
            project_id=pid,
            company_id=cid,
            event_type=event_type,
            payload=payload,
            actor=actor,
        )
        db.add(row)
        db.flush()
        return {
            "id": str(row.id),
            "event_type": row.event_type,
            "project_id": str(pid) if pid else None,
            "company_id": str(cid) if cid else None,
            "payload": row.payload,
            "actor": row.actor,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "persisted": True,
        }


_bus: WorkflowEventBus | None = None


def get_event_bus() -> WorkflowEventBus:
    global _bus
    if _bus is None:
        _bus = WorkflowEventBus()
    return _bus
