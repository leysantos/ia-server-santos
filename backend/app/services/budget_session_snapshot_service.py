"""Persistência de sessões ativas de orçamento no PostgreSQL (B18)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pricing.budget.budget_session import BudgetSession

logger = logging.getLogger(__name__)


def save_session_snapshot(session: BudgetSession) -> bool:
    """Grava snapshot da sessão — falha silenciosa se DB indisponível."""
    try:
        from core.database.connection import SessionLocal, is_db_enabled
        from core.database.models import BudgetSessionSnapshot

        if not is_db_enabled():
            return False

        payload = session.to_dict()
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            row = db.get(BudgetSessionSnapshot, session.id)
            if row:
                row.payload = payload
                row.updated_at = now
            else:
                db.add(
                    BudgetSessionSnapshot(
                        session_id=session.id,
                        payload=payload,
                        updated_at=now,
                    )
                )
            db.commit()
            return True
        finally:
            db.close()
    except Exception:
        logger.debug("save_session_snapshot falhou para %s", session.id[:8], exc_info=True)
        return False


def restore_session_snapshot(session_id: str) -> BudgetSession | None:
    """Restaura sessão do snapshot e recoloca no SESSION_STORE."""
    try:
        from app.services.budget_db_service import session_from_payload
        from core.database.connection import SessionLocal, is_db_enabled
        from core.database.models import BudgetSessionSnapshot

        if not is_db_enabled():
            return None

        db = SessionLocal()
        try:
            row = db.get(BudgetSessionSnapshot, session_id)
            if not row or not row.payload:
                return None
            return session_from_payload(dict(row.payload))
        finally:
            db.close()
    except Exception:
        logger.debug("restore_session_snapshot falhou para %s", session_id[:8], exc_info=True)
        return None


def delete_session_snapshot(session_id: str) -> bool:
    try:
        from core.database.connection import SessionLocal, is_db_enabled
        from core.database.models import BudgetSessionSnapshot

        if not is_db_enabled():
            return False

        db = SessionLocal()
        try:
            row = db.get(BudgetSessionSnapshot, session_id)
            if row:
                db.delete(row)
                db.commit()
                return True
            return False
        finally:
            db.close()
    except Exception:
        logger.debug("delete_session_snapshot falhou", exc_info=True)
        return False
