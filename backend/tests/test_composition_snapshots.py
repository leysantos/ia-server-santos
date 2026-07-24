"""Testes — cache global de composição aberta."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import Base, CompositionOpenCache
from pricing.budget.composition_snapshot_service import (
    composition_fetch_key,
    get_batch_compositions,
    load_cache_map,
    sync_missing_snapshots,
    upsert_cache_entry,
)
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.models.budget_metadata import BudgetProjectMetadata


def _sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _service_item(code: str = "97063") -> BudgetItem:
    item = BudgetItem(
        row_id="svc1",
        code="1.1.1",
        name="Serviço teste",
        level=1,
        source_code=code,
        source_base="SINAPI",
        unit="m2",
        quantity=10.0,
        unit_cost=100.0,
        unit_price=120.0,
        total_price=1200.0,
        item_type=BudgetItemType.COMPOSITION,
    )
    item.metadata["price_reference"] = "BR-2024-01"
    return item


@pytest.fixture()
def db():
    session = _sqlite_session()
    yield session
    session.close()


def test_composition_fetch_key():
    assert composition_fetch_key("97063", "BR-2024-01", "sp") == "97063|BR-2024-01|SP"


def test_upsert_and_load_cache(db):
    detail = {"code": "97063", "description": "CPU", "unit": "m2", "total_price": 1, "items": []}
    upsert_cache_entry(db, "97063", "BR-2024-01", "SP", detail)
    db.commit()

    stored = load_cache_map(db, [("97063", "BR-2024-01", "SP")])
    key = composition_fetch_key("97063", "BR-2024-01", "SP")
    assert key in stored
    assert stored[key]["code"] == "97063"

    row = db.query(CompositionOpenCache).one()
    assert row.composition_code == "97063"


def test_get_batch_compositions_uses_cache(db, monkeypatch):
    detail = {
        "code": "97063",
        "description": "CPU",
        "unit": "m2",
        "total_price": 10,
        "items": [{"code": "i1", "description": "insumo"}],
    }
    upsert_cache_entry(db, "97063", "BR-2024-01", "SP", detail)
    db.commit()

    meta = BudgetProjectMetadata.from_dict(
        {
            "price_bases": [
                {"source": "sinapi", "reference": "BR-2024-01", "uf": "SP", "enabled": True}
            ]
        }
    )
    roots = [_service_item()]

    monkeypatch.setattr(
        "pricing.budget.composition_snapshot_service._resolve_one",
        lambda *a, **k: pytest.fail("should not hit bank"),
    )

    result = get_batch_compositions(
        db,
        roots=roots,
        meta=meta,
        backfill=False,
    )
    assert result["from_cache"] == 1
    assert result["from_db"] == 1
    assert result["from_bank"] == 0
    assert len(result["snapshots"]) == 1


def test_sync_missing_snapshots_skips_existing(db, monkeypatch):
    detail = {"code": "97063", "description": "CPU", "unit": "m2", "total_price": 1, "items": []}
    upsert_cache_entry(db, "97063", "BR-2024-01", "SP", detail)
    db.commit()

    meta = BudgetProjectMetadata.from_dict(
        {
            "price_bases": [
                {"source": "sinapi", "reference": "BR-2024-01", "uf": "SP", "enabled": True}
            ]
        }
    )

    monkeypatch.setattr(
        "pricing.budget.composition_snapshot_service._resolve_one",
        lambda *a, **k: pytest.fail("should not fetch"),
    )

    stats = sync_missing_snapshots(db, None, [_service_item()], meta)
    assert stats["fetched"] == 0
    assert stats["required"] == 1


def test_upsert_cache_idempotent(db):
    detail_v1 = {"code": "97063", "description": "CPU v1", "unit": "m2", "total_price": 1, "items": []}
    detail_v2 = {"code": "97063", "description": "CPU v2", "unit": "m2", "total_price": 2, "items": []}

    upsert_cache_entry(db, "97063", "BR-2024-01", "SP", detail_v1)
    db.commit()
    upsert_cache_entry(db, "97063", "BR-2024-01", "SP", detail_v2)
    db.commit()

    rows = db.query(CompositionOpenCache).all()
    assert len(rows) == 1
    assert rows[0].detail_json["description"] == "CPU v2"


def test_global_cache_shared_across_budgets(db):
    """Segundo orçamento reutiliza cache sem nova ida ao price_bank."""
    detail = {"code": "97063", "description": "CPU", "unit": "m2", "total_price": 1, "items": []}
    upsert_cache_entry(db, "97063", "BR-2024-01", "SP", detail)
    db.commit()

    meta = BudgetProjectMetadata.from_dict(
        {
            "price_bases": [
                {"source": "sinapi", "reference": "BR-2024-01", "uf": "SP", "enabled": True}
            ]
        }
    )

    result = get_batch_compositions(db, roots=[_service_item()], meta=meta)
    assert result["from_cache"] == 1
    assert result["from_bank"] == 0
