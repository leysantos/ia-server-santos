"""Testes fluxo aditivo — baseline + revisões (B6)."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.database.workflow_models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.budget_db_service import get_budget, save_budget
from app.services.budget_revision_service import (
    BudgetBaselineFrozenError,
    compare_with_baseline,
    create_revision,
    freeze_baseline,
    list_revisions,
)
from core.database.models import Base, BudgetDocument, User


def _setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(
        id=uuid.uuid4(),
        username="rev_user",
        email="rev@test.local",
        full_name="Rev User",
        role="dev_user",
        password_hash="x",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return db, user


def _payload(total: float = 1000.0) -> dict:
    return {
        "session_id": uuid.uuid4().hex,
        "title": "Obra revisão",
        "items": [],
        "rows": [
            {
                "code": "1.1.1",
                "name": "Serviço A",
                "level": 3,
                "quantity": 1,
                "unit": "m2",
                "unit_cost": total,
                "unit_price": total,
                "total_price": total,
                "total_effective": total,
                "row_type": "COMPOSICAO",
                "row_id": "r1",
            }
        ],
        "grand_total": total,
        "project": {"obra_type": "RF"},
    }


def test_freeze_and_create_revision():
    db, user = _setup_db()
    saved = save_budget(db, _payload(1000), user=user)
    doc_id = saved["db_id"]

    frozen = freeze_baseline(db, doc_id, user=user)
    assert frozen["revision"]["baseline_frozen"] is True

    rev = create_revision(db, doc_id, user=user)
    assert rev["revision"]["revision_number"] == 1
    assert rev["session"]["db_id"] != doc_id

    items = list_revisions(db, doc_id, user=user)
    assert len(items) == 2


def test_frozen_baseline_blocks_save():
    db, user = _setup_db()
    saved = save_budget(db, _payload(), user=user)
    freeze_baseline(db, saved["db_id"], user=user)

    with pytest.raises(BudgetBaselineFrozenError):
        save_budget(db, _payload(2000), budget_id=saved["db_id"], user=user)


def test_baseline_compare():
    db, user = _setup_db()
    saved = save_budget(db, _payload(1000), user=user)
    freeze_baseline(db, saved["db_id"], user=user)
    rev = create_revision(db, saved["db_id"], user=user)
    rev_id = rev["session"]["db_id"]

    updated_payload = _payload(1200)
    save_budget(db, updated_payload, budget_id=rev_id, user=user)

    cmp = compare_with_baseline(db, rev_id, user=user)
    assert cmp["comparison"]["delta_grand_total"] == 200.0
