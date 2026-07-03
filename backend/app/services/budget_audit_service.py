"""Persistência da trilha de auditoria de orçamento (B7/B16)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from core.database.models import BudgetAuditLog, User

logger = logging.getLogger(__name__)


def _parse_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def persist_session_audit_entries(
    db: Session,
    session_id: str,
    entries: list[dict[str, Any]],
    *,
    budget_document_id: str | uuid.UUID | None = None,
    user: User | None = None,
) -> int:
    """Grava entradas de audit_log da sessão no banco."""
    if not entries:
        return 0
    doc_id = _parse_uuid(budget_document_id)
    user_id = user.id if user else None
    count = 0
    for entry in entries:
        action = str(entry.get("action") or "unknown")
        row = BudgetAuditLog(
            id=uuid.uuid4(),
            budget_document_id=doc_id,
            session_id=session_id,
            user_id=user_id,
            action=action,
            row_code=entry.get("row_code"),
            row_id=entry.get("row_id"),
            field=entry.get("field"),
            old_value={"value": entry.get("old_value")} if "old_value" in entry else None,
            new_value={"value": entry.get("new_value")} if "new_value" in entry else None,
            meta={
                k: v
                for k, v in entry.items()
                if k
                not in {
                    "action",
                    "row_code",
                    "row_id",
                    "field",
                    "old_value",
                    "new_value",
                    "at",
                }
            }
            or None,
        )
        db.add(row)
        count += 1
    if count:
        db.commit()
    return count


def persist_audit_delta(
    db: Session,
    session: Any,
    session_id: str,
    audit_before: int,
    *,
    user: User | None = None,
) -> int:
    """Persiste entradas novas do audit_log da sessão desde audit_before."""
    if session is None:
        return 0
    new_entries = session.audit_log[audit_before:]
    if not new_entries:
        return 0
    try:
        return persist_session_audit_entries(
            db,
            session_id,
            new_entries,
            budget_document_id=getattr(session, "db_id", None),
            user=user,
        )
    except Exception:
        logger.exception("Falha ao persistir audit_log (%s)", session_id[:8])
        return 0


def list_audit_trail(
    db: Session,
    *,
    session_id: str | None = None,
    budget_document_id: str | uuid.UUID | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = db.query(BudgetAuditLog).order_by(BudgetAuditLog.created_at.desc())
    if session_id:
        query = query.filter(BudgetAuditLog.session_id == session_id)
    doc_id = _parse_uuid(budget_document_id)
    if doc_id:
        query = query.filter(BudgetAuditLog.budget_document_id == doc_id)
    rows = query.limit(limit).all()
    return [
        {
            "id": str(r.id),
            "action": r.action,
            "session_id": r.session_id,
            "budget_document_id": str(r.budget_document_id) if r.budget_document_id else None,
            "user_id": str(r.user_id) if r.user_id else None,
            "row_code": r.row_code,
            "row_id": r.row_id,
            "field": r.field,
            "old_value": (r.old_value or {}).get("value"),
            "new_value": (r.new_value or {}).get("value"),
            "meta": r.meta,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
