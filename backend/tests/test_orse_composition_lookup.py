"""Lookup de composições ORSE com código contendo '/' (ex. 00084/ORSE)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pricing.budget.price_bank_store import PriceBankStore, resolve_open_composition_key

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("DB_ENABLED", "false")

ORSE_REF = "BR-ORSE-2026-04"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("DB_ENABLED", "false")
    from config.settings import reload_settings

    reload_settings()
    from app.main import app

    return TestClient(app)


def _orse_open_exists() -> bool:
    root = Path(__file__).resolve().parents[1]
    return (root / "knowledge" / "price_bank" / ORSE_REF / "compositions_open.json").exists()


@pytest.mark.skipif(not _orse_open_exists(), reason="ORSE price bank not imported locally")
def test_get_open_composition_orse_full_code():
    store = PriceBankStore.for_reference(ORSE_REF)
    comp = store.get_open_composition("00084/ORSE", uf="SE")
    assert comp is not None
    assert comp.get("code") == "00084/ORSE"
    assert comp.get("items")


@pytest.mark.skipif(not _orse_open_exists(), reason="ORSE price bank not imported locally")
def test_get_open_composition_orse_truncated_path_code():
    """Simula path truncado quando %2F vira / no roteamento HTTP."""
    store = PriceBankStore.for_reference(ORSE_REF)
    comp = store.get_open_composition("00084", uf="SE")
    assert comp is not None
    assert comp.get("code") == "00084/ORSE"


def test_resolve_open_composition_key_orse_variants():
    open_data = {"00084/ORSE": {"code": "00084/ORSE", "items": []}}
    assert resolve_open_composition_key("00084/ORSE", open_data) == "00084/ORSE"
    assert resolve_open_composition_key("00084", open_data) == "00084/ORSE"
    assert resolve_open_composition_key("84", open_data) == "00084/ORSE"
    assert resolve_open_composition_key("99999", open_data) is None


def test_composition_query_route(client):
    """GET /sync/bank/composition?code= evita quebra de path com '/'."""
    if not _orse_open_exists():
        pytest.skip("ORSE price bank not imported locally")
    resp = client.get(
        "/pricing/sync/bank/composition",
        params={"code": "00084/ORSE", "reference": ORSE_REF, "uf": "SE"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("code") == "00084/ORSE"
    assert body.get("items")
