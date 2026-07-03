"""Helpers de trilha de auditoria de orçamento (B7/B16)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def audit_entry(action: str, **fields: Any) -> dict[str, Any]:
    return {
        "action": action,
        "at": datetime.now(timezone.utc).isoformat(),
        **{k: v for k, v in fields.items() if v is not None},
    }


def append_audit(session: Any, entry: dict[str, Any]) -> None:
    session.audit_log.append(entry)


def service_snapshot(item: Any) -> dict[str, Any] | None:
    if not item:
        return None
    return {
        "row_id": getattr(item, "row_id", ""),
        "code": getattr(item, "code", ""),
        "name": getattr(item, "name", ""),
        "source_code": getattr(item, "source_code", ""),
        "source_base": getattr(item, "source_base", ""),
        "quantity": getattr(item, "quantity", 0),
        "unit": getattr(item, "unit", ""),
        "unit_cost": getattr(item, "unit_cost", 0),
    }
