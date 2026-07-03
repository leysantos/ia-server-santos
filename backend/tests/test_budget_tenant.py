"""B27 — isolamento de orçamentos por empresa (empresa_id)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import core.database.workflow_models  # noqa: F401
from core.database.models import BudgetDocument, User
from pricing.budget.budget_session import SESSION_STORE


@pytest.fixture
def tenant_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("MINIO_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tenant.db'}")

    from config.settings import reload_settings

    reload_settings()

    from tests.budget_test_db import rebind_test_database

    rebind_test_database(f"sqlite:///{tmp_path / 'tenant.db'}")
    SESSION_STORE._sessions.clear()

    from core.database.connection import init_db

    init_db()

    from app.main import app

    yield TestClient(app)

    SESSION_STORE._sessions.clear()


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_company(client: TestClient, headers: dict, slug: str) -> str:
    r = client.post(
        "/workflow/companies",
        json={"nome": f"Empresa {slug}", "slug": slug},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_budget_tenant_isolation(tenant_client: TestClient):
    admin_h = _login(tenant_client, "admin", "Admin@2026!")
    company_a = _create_company(tenant_client, admin_h, "empresa-a")
    company_b = _create_company(tenant_client, admin_h, "empresa-b")

    created = tenant_client.post(
        "/pricing/budget/new-from-skeleton",
        params={"skeleton_id": "sk-b12-piloto-passarela", "projeto": "Tenant A"},
        headers={**admin_h, "X-Tenant-Id": company_a},
    )
    assert created.status_code == 200
    session = created.json()
    sid = session["session_id"]

    saved = tenant_client.post(
        "/pricing/budget/saved",
        json={"payload": session, "title": "Orçamento Empresa A"},
        headers={**admin_h, "X-Tenant-Id": company_a},
    )
    assert saved.status_code == 200
    budget_id = saved.json()["db_id"]

    list_a = tenant_client.get(
        "/pricing/budget/saved",
        headers={**admin_h, "X-Tenant-Id": company_a},
    )
    assert list_a.status_code == 200
    ids_a = {item["id"] for item in list_a.json()["items"]}
    assert budget_id in ids_a

    list_b = tenant_client.get(
        "/pricing/budget/saved",
        headers={**admin_h, "X-Tenant-Id": company_b},
    )
    assert list_b.status_code == 200
    ids_b = {item["id"] for item in list_b.json()["items"]}
    assert budget_id not in ids_b

    get_wrong = tenant_client.get(
        f"/pricing/budget/saved/{budget_id}",
        headers={**admin_h, "X-Tenant-Id": company_b},
    )
    assert get_wrong.status_code == 404

    # Sessão ainda editável no tenant correto
    patch = tenant_client.post(
        f"/pricing/budget/{sid}/lock",
        headers=admin_h,
    )
    assert patch.status_code == 200
