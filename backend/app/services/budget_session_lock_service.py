"""Lock exclusivo de edição por session_id (B28) — complementa B2 version lock."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config.settings import get_settings
from core.database.models import BudgetSessionLock, User


class BudgetSessionLockConflictError(Exception):
    def __init__(self, holder_user_id: uuid.UUID | None, expires_at: datetime | None):
        self.holder_user_id = holder_user_id
        self.expires_at = expires_at
        super().__init__("Sessão bloqueada por outro usuário")


DEFAULT_TTL_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Normaliza datetimes do ORM (sqlite pode retornar naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _auth_active() -> bool:
    return bool(get_settings().auth_enabled)


def acquire_lock(
    db: Session,
    session_id: str,
    user: User | None,
    *,
    budget_document_id: uuid.UUID | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict:
    if not _auth_active() or user is None:
        return {"locked": False, "reason": "auth_disabled"}

    now = _now()
    row = db.get(BudgetSessionLock, session_id)
    if row and _as_utc(row.expires_at) > now and row.user_id != user.id:
        raise BudgetSessionLockConflictError(row.user_id, row.expires_at)

    expires = now + timedelta(seconds=ttl_seconds)
    if row:
        row.user_id = user.id
        row.expires_at = expires
        row.locked_at = now
        if budget_document_id:
            row.budget_document_id = budget_document_id
    else:
        row = BudgetSessionLock(
            session_id=session_id,
            user_id=user.id,
            locked_at=now,
            expires_at=expires,
            budget_document_id=budget_document_id,
        )
        db.add(row)
    db.commit()
    return {
        "session_id": session_id,
        "user_id": str(user.id),
        "expires_at": expires.isoformat(),
        "ttl_seconds": ttl_seconds,
    }


def renew_lock(db: Session, session_id: str, user: User | None, *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict:
    if not _auth_active() or user is None:
        return {"renewed": False}
    row = db.get(BudgetSessionLock, session_id)
    now = _now()
    if not row or _as_utc(row.expires_at) <= now:
        return acquire_lock(db, session_id, user, ttl_seconds=ttl_seconds)
    if row.user_id != user.id:
        raise BudgetSessionLockConflictError(row.user_id, row.expires_at)
    row.expires_at = now + timedelta(seconds=ttl_seconds)
    db.commit()
    return {"session_id": session_id, "expires_at": row.expires_at.isoformat(), "renewed": True}


def release_lock(db: Session, session_id: str, user: User | None) -> bool:
    if not _auth_active() or user is None:
        return True
    row = db.get(BudgetSessionLock, session_id)
    if not row:
        return True
    if row.user_id != user.id:
        raise BudgetSessionLockConflictError(row.user_id, row.expires_at)
    db.delete(row)
    db.commit()
    return True


def assert_session_lock(db: Session, session_id: str, user: User | None) -> None:
    if not _auth_active() or user is None:
        return
    row = db.get(BudgetSessionLock, session_id)
    if not row:
        return
    now = _now()
    if _as_utc(row.expires_at) <= now:
        db.delete(row)
        db.commit()
        return
    if row.user_id != user.id:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Outro usuário está editando este orçamento.",
                "holder_user_id": str(row.user_id),
                "expires_at": row.expires_at.isoformat(),
            },
        )


def lock_status(db: Session, session_id: str, user: User | None) -> dict:
    if not _auth_active():
        return {"active": False}
    row = db.get(BudgetSessionLock, session_id)
    now = _now()
    if not row or _as_utc(row.expires_at) <= now:
        return {"active": False, "session_id": session_id}
    return {
        "active": True,
        "session_id": session_id,
        "holder_user_id": str(row.user_id),
        "is_mine": user is not None and row.user_id == user.id,
        "expires_at": row.expires_at.isoformat(),
    }
