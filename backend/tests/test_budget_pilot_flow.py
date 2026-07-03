"""B12 — fluxo piloto orçamento (template → edição → persistência → export)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pricing.bootstrap import ensure_providers_registered, load_default_bases, reset_providers
from pricing.budget.budget_session import SESSION_STORE

DATA_DIR = Path(__file__).resolve().parent.parent / "pricing" / "data"


@pytest.fixture
def pilot_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("MINIO_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'pilot.db'}")

    from config.settings import reload_settings

    reload_settings()

    db_url = f"sqlite:///{tmp_path / 'pilot.db'}"
    from tests.budget_test_db import rebind_test_database

    rebind_test_database(db_url)

    import core.database.workflow_models  # noqa: F401

    import core.workflow.storage.client as storage_client

    storage_client._storage = None

    reset_providers()
    SESSION_STORE._sessions.clear()
    ensure_providers_registered()
    load_default_bases(DATA_DIR)

    from core.database.connection import init_db

    init_db()

    from app.main import app

    yield TestClient(app)

    SESSION_STORE._sessions.clear()


@pytest.fixture
def auth_headers(pilot_client: TestClient) -> dict[str, str]:
    login = pilot_client.post(
        "/auth/login",
        json={"username": "admin", "password": "Admin@2026!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _pick_editable_row(session: dict) -> dict | None:
    for row in session.get("rows") or []:
        if row.get("editable") and float(row.get("unit_price") or 0) > 0:
            return row
    for row in session.get("rows") or []:
        if row.get("editable"):
            return row
    return None


def test_pilot_new_template_edit_save_export(pilot_client: TestClient, auth_headers: dict[str, str]):
    """4.1–4.5 checklist: sessão piloto, edição, persistência e export."""
    created = pilot_client.post(
        "/pricing/budget/new-from-skeleton",
        params={
            "skeleton_id": "sk-b12-piloto-passarela",
            "projeto": "Obra Piloto B12 — Passarela",
            "obra_type": "RF",
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    session = created.json()
    sid = session["session_id"]
    assert session.get("rows") or session.get("items")
    assert len(session.get("rows") or []) >= 4

    row = _pick_editable_row(session)
    if row:
        field = "quantity" if float(row.get("unit_price") or 0) > 0 else "name"
        value = float(row.get("quantity") or 1) + 1 if field == "quantity" else f"{row.get('name', 'Item')} (piloto)"
        patched = pilot_client.patch(
            f"/pricing/budget/{sid}/cell",
            json={
                "row_id": row["row_id"],
                "code": row.get("code"),
                "field": field,
                "value": value,
            },
            headers=auth_headers,
        )
        assert patched.status_code == 200, patched.text
        session = patched.json()

    saved = pilot_client.post(
        "/pricing/budget/saved",
        json={
            "title": session.get("title") or "Obra Piloto B12",
            "payload": session,
        },
        headers=auth_headers,
    )
    assert saved.status_code == 200, saved.text
    db_id = saved.json().get("db_id")
    assert db_id

    listed = pilot_client.get("/pricing/budget/saved", headers=auth_headers)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json().get("items") or []}
    assert db_id in ids

    xlsx = pilot_client.get(
        f"/pricing/budget/{sid}/export/xlsx/orc_sintetico",
        headers=auth_headers,
    )
    assert xlsx.status_code == 200, xlsx.text[:200]
    assert xlsx.content[:2] == b"PK"

    pdf = pilot_client.get(
        f"/pricing/budget/{sid}/export/pdf/orc_sintetico",
        headers=auth_headers,
    )
    assert pdf.status_code == 200, pdf.text[:200]
    assert pdf.content[:4] == b"%PDF"

    audit = pilot_client.get(f"/pricing/budget/{sid}/audit", headers=auth_headers)
    assert audit.status_code == 200
    assert "items" in audit.json()


def test_pilot_from_skeleton_b12(pilot_client: TestClient, auth_headers: dict[str, str]):
    """Esqueleto B12 — passarela municipal."""
    created = pilot_client.post(
        "/pricing/budget/new-from-skeleton",
        params={
            "skeleton_id": "sk-b12-piloto-passarela",
            "projeto": "Passarela piloto B12",
            "obra_type": "RF",
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body.get("session_id")
    assert len(body.get("rows") or []) >= 4


def test_pilot_bdi_and_restore(pilot_client: TestClient, auth_headers: dict[str, str]):
    created = pilot_client.post(
        "/pricing/budget/new-from-skeleton",
        params={
            "skeleton_id": "sk-b12-piloto-passarela",
            "projeto": "Piloto BDI",
            "obra_type": "RF",
        },
        headers=auth_headers,
    )
    assert created.status_code == 200
    session = created.json()
    sid = session["session_id"]
    assert session.get("rows")

    bdi = pilot_client.patch(
        f"/pricing/budget/{sid}/bdi",
        json={"obra_type": "RF", "profile_id": "seminf_table"},
        headers=auth_headers,
    )
    assert bdi.status_code == 200, bdi.text
    payload = bdi.json()
    assert payload.get("rows")

    SESSION_STORE._sessions.pop(sid, None)
    restored = pilot_client.post(
        "/pricing/budget/restore",
        json={"payload": payload},
        headers=auth_headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json().get("session_id")

    got = pilot_client.get(f"/pricing/budget/{restored.json()['session_id']}", headers=auth_headers)
    assert got.status_code == 200


def _first_etapa_code(session: dict) -> str:
    for row in session.get("rows") or []:
        if row.get("row_type") == "ETAPA" and int(row.get("level") or 0) == 0:
            return str(row.get("code") or "1")
    return "1"


def _ppd_template_available() -> bool:
    try:
        from pricing.budget.ppd_template_registry import resolve_template

        resolve_template()
        return True
    except FileNotFoundError:
        return False


def test_pilot_section4_field_checklist(pilot_client: TestClient, auth_headers: dict[str, str]):
    """§4 checklist campo — serviço, cronograma, ComD/SemD, exports analítico/ABC/MCQ."""
    created = pilot_client.post(
        "/pricing/budget/new-from-skeleton",
        params={
            "skeleton_id": "sk-b12-piloto-passarela",
            "projeto": "Piloto §4 Campo",
            "obra_type": "RF",
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    session = created.json()
    sid = session["session_id"]
    etapa = _first_etapa_code(session)

    added = pilot_client.post(
        f"/pricing/budget/{sid}/services",
        json={
            "etapa_code": etapa,
            "code": "PILOTO-S4",
            "description": "Serviço checklist §4",
            "unit": "vb",
            "price": 2500.0,
            "source": "manual",
            "quantity": 1.0,
        },
        headers=auth_headers,
    )
    assert added.status_code == 200, added.text
    session = added.json()

    synced = pilot_client.post(
        f"/pricing/budget/{sid}/schedule/sync",
        headers=auth_headers,
    )
    assert synced.status_code == 200, synced.text
    schedule = synced.json().get("schedule") or {}
    assert len(schedule.get("tasks") or []) >= 1

    bdi = pilot_client.patch(
        f"/pricing/budget/{sid}/bdi",
        json={"obra_type": "RF", "profile_id": "seminf_table"},
        headers=auth_headers,
    )
    assert bdi.status_code == 200, bdi.text
    session = bdi.json()
    project_bdi = (session.get("project") or {}).get("bdi") or {}
    assert project_bdi.get("rate_com_desoneracao") is not None
    assert project_bdi.get("rate_sem_desoneracao") is not None

    for doc_type, kind in [
        ("orc_sintetico", "xlsx"),
        ("orc_analitico", "xlsx"),
        ("curva_abc", "xlsx"),
        ("mcq", "xlsx"),
        ("orc_sintetico", "pdf"),
        ("orc_analitico", "pdf"),
        ("curva_abc", "pdf"),
        ("mcq", "pdf"),
        ("cronograma", "xlsx"),
        ("cronograma", "pdf"),
    ]:
        path = f"/pricing/budget/{sid}/export/{kind}/{doc_type}"
        resp = pilot_client.get(path, headers=auth_headers)
        assert resp.status_code == 200, f"{path}: {resp.text[:200]}"
        if kind == "xlsx":
            assert resp.content[:2] == b"PK", doc_type
        else:
            assert resp.content[:4] == b"%PDF", doc_type

    if _ppd_template_available():
        xlsm = pilot_client.get(f"/pricing/budget/{sid}/export/xlsm", headers=auth_headers)
        assert xlsm.status_code == 200, xlsm.text[:200]
        assert xlsm.content[:2] == b"PK", "xlsm export"

    compliance = pilot_client.get(
        f"/pricing/budget/{sid}/export/compliance-pack.json",
        headers=auth_headers,
    )
    assert compliance.status_code == 200, compliance.text[:200]
    pack = compliance.json()
    assert "checklist_lei_14133" in pack
    assert any(c["id"] == "L3" for c in pack["checklist_lei_14133"])

    bdi_val = pilot_client.get(f"/pricing/budget/{sid}/bdi/validation", headers=auth_headers)
    assert bdi_val.status_code == 200
    assert bdi_val.json().get("status") in ("ok", "warning", "error")


@pytest.mark.skipif(
    os.environ.get("RUN_BUDGET_PILOT_LIVE") != "1",
    reason="Defina RUN_BUDGET_PILOT_LIVE=1 para validar price_bank ao vivo",
)
def test_pilot_cpu_search_live(pilot_client: TestClient, auth_headers: dict[str, str]):
    """4.3 — busca CPU requer price_bank indexado (ambiente com make index-price-bases)."""
    refs = pilot_client.get("/pricing/sync/bank/references", headers=auth_headers)
    assert refs.status_code == 200
    if not (refs.json().get("references") or []):
        pytest.skip("price_bank vazio — rode make index-price-bases")

    search = pilot_client.get(
        "/pricing/sync/bank/open-compositions/search",
        params={"q": "concreto", "uf": "SP", "limit": 5},
        headers=auth_headers,
    )
    assert search.status_code == 200
    items = search.json().get("items") or search.json().get("results") or []
    assert len(items) >= 1
