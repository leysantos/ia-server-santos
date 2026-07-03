"""B28 — lock de edição concorrente por session_id."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import core.database.workflow_models  # noqa: F401
from pricing.budget.budget_session import SESSION_STORE


@pytest.fixture
def lock_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'lock.db'}")

    from config.settings import reload_settings

    reload_settings()

    from tests.budget_test_db import rebind_test_database

    rebind_test_database(f"sqlite:///{tmp_path / 'lock.db'}")
    import core.database.workflow_models  # noqa: F401

    SESSION_STORE._sessions.clear()

    from core.database.connection import init_db

    init_db()

    from app.main import app

    yield TestClient(app)

    SESSION_STORE._sessions.clear()


def _headers(client: TestClient) -> dict[str, str]:
    login = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_session_lock_blocks_other_user(lock_client: TestClient, monkeypatch):
    headers = _headers(lock_client)

    created = lock_client.post(
        "/pricing/budget/new-from-skeleton",
        params={"skeleton_id": "sk-b12-piloto-passarela"},
        headers=headers,
    )
    assert created.status_code == 200
    sid = created.json()["session_id"]

    acq = lock_client.post(f"/pricing/budget/{sid}/lock", headers=headers)
    assert acq.status_code == 200

    # Simula segundo usuário — criar user dev e login
    from core.database.connection import session_scope
    from core.database.models import User
    from core.auth.passwords import hash_password

    with session_scope() as db:
        if not db.query(User).filter(User.username == "dev2").first():
            db.add(
                User(
                    username="dev2",
                    email="dev2@test.local",
                    full_name="Dev 2",
                    password_hash=hash_password("Dev2@2026!"),
                    role="dev_user",
                    is_active=True,
                )
            )
            db.commit()

    login2 = lock_client.post("/auth/login", json={"username": "dev2", "password": "Dev2@2026!"})
    assert login2.status_code == 200
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    conflict = lock_client.post(f"/pricing/budget/{sid}/lock", headers=headers2)
    assert conflict.status_code == 409

    cell = lock_client.patch(
        f"/pricing/budget/{sid}/cell",
        json={"code": "1.1", "field": "quantity", "value": 1},
        headers=headers2,
    )
    assert cell.status_code == 409

    release = lock_client.delete(f"/pricing/budget/{sid}/lock", headers=headers)
    assert release.status_code == 200

    acq2 = lock_client.post(f"/pricing/budget/{sid}/lock", headers=headers2)
    assert acq2.status_code == 200
