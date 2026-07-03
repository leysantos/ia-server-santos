"""Testes de ownership e versionamento de orçamentos persistidos."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.database.workflow_models  # noqa: F401 — registra Company para FK de Project

from app.services.budget_db_service import (
    BudgetVersionConflictError,
    delete_budget,
    get_budget,
    list_budgets,
    save_budget,
)
from core.database.models import Base, BudgetDocument, User


def _setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user_a = User(
        id=uuid.uuid4(),
        username="user_a",
        email="a@test.local",
        full_name="User A",
        role="dev_user",
        password_hash="x",
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        username="user_b",
        email="b@test.local",
        full_name="User B",
        role="dev_user",
        password_hash="x",
        is_active=True,
    )
    db.add_all([user_a, user_b])
    db.commit()
    return db, user_a, user_b


def _payload(session_id: str = "sess-1") -> dict:
    return {
        "session_id": session_id,
        "title": "Obra teste",
        "items": [],
        "grand_total": 1000.0,
        "project": {"obra_type": "RF"},
    }


def test_save_assigns_user_id_on_create():
    db, user_a, _user_b = _setup_db()
    saved = save_budget(db, _payload(), user=user_a)
    assert saved["document_version"] == 1
    assert saved["user_id"] == str(user_a.id)


def test_list_filters_by_owner():
    db, user_a, user_b = _setup_db()
    save_budget(db, _payload("s1"), user=user_a)
    save_budget(db, _payload("s2"), user=user_b)

    items_a = list_budgets(db, user=user_a)
    items_b = list_budgets(db, user=user_b)
    assert len(items_a) == 1
    assert len(items_b) == 1
    assert items_a[0]["session_id"] == "s1"
    assert items_b[0]["session_id"] == "s2"


def test_user_cannot_read_foreign_budget():
    db, user_a, user_b = _setup_db()
    saved = save_budget(db, _payload(), user=user_a)
    assert get_budget(db, saved["db_id"], user=user_b) is None


def test_version_conflict_on_stale_update():
    db, user_a, _user_b = _setup_db()
    saved = save_budget(db, _payload(), user=user_a)
    doc_id = saved["db_id"]

    with pytest.raises(BudgetVersionConflictError) as exc:
        save_budget(
            db,
            _payload(),
            budget_id=doc_id,
            user=user_a,
            expected_version=0,
        )
    assert exc.value.current_version == 1

    updated = save_budget(
        db,
        _payload(),
        budget_id=doc_id,
        user=user_a,
        expected_version=1,
    )
    assert updated["document_version"] == 2


def test_delete_respects_ownership():
    db, user_a, user_b = _setup_db()
    saved = save_budget(db, _payload(), user=user_a)
    assert delete_budget(db, saved["db_id"], user=user_b) is False
    assert delete_budget(db, saved["db_id"], user=user_a) is True
    assert db.get(BudgetDocument, uuid.UUID(saved["db_id"])) is None
