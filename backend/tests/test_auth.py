"""Testes de autenticação JWT."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "true")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key")
os.environ.setdefault("DB_ENABLED", "false")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth_test.db'}")

    from config.settings import reload_settings

    reload_settings()

    from core.database.connection import engine
    from core.database.migrate_auth import migrate_auth
    from core.database.migrate_user_roles import migrate_user_roles
    import core.database.workflow_models  # noqa: F401

    migrate_auth(engine)
    migrate_user_roles(engine)

    from app.main import app

    return TestClient(app)


def test_auth_status(client):
    r = client.get("/auth/status")
    assert r.status_code == 200
    assert r.json()["auth_enabled"] is True


def test_login_and_me(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert r.json()["user"]["role"] == "admin"

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "admin"


def test_protected_route_without_token(client):
    r = client.get("/auth/users")
    assert r.status_code == 401


def test_admin_lists_users(client):
    login = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    token = login.json()["access_token"]
    r = client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    usernames = {u["username"] for u in r.json()["users"]}
    assert usernames == {"admin", "dev_user1", "dev_user2"}


def test_admin_lists_roles(client):
    login = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    token = login.json()["access_token"]
    r = client.get("/auth/roles", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    slugs = {role["slug"] for role in r.json()["roles"]}
    assert "admin" in slugs
    assert "dev_user" in slugs


def test_create_custom_role_and_user(client):
    login = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    role = client.post(
        "/auth/roles",
        headers=headers,
        json={
            "slug": "engenheiro",
            "label": "Engenheiro",
            "module_permissions": {
                "chat": {"hidden": False, "blocked": False},
                "budget": {"hidden": True, "blocked": False},
            },
        },
    )
    assert role.status_code == 200

    user = client.post(
        "/auth/users",
        headers=headers,
        json={
            "username": "eng1",
            "password": "Eng@2026!",
            "role": "engenheiro",
        },
    )
    assert user.status_code == 200
    assert user.json()["user"]["role"] == "engenheiro"
    assert user.json()["user"]["module_permissions"]["budget"]["hidden"] is True


def test_dev_user_cannot_list_users(client):
    login = client.post("/auth/login", json={"username": "dev_user1", "password": "Dev@2026!"})
    token = login.json()["access_token"]
    r = client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_admin_updates_user_module_permissions(client):
    login = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    users = client.get("/auth/users", headers=headers).json()["users"]
    dev = next(u for u in users if u["username"] == "dev_user1")

    updated = client.patch(
        f"/auth/users/{dev['id']}",
        headers=headers,
        json={
            "full_name": "Dev Atualizado",
            "module_permissions": {
                "chat": {"hidden": False, "blocked": False},
                "budget": {"hidden": True, "blocked": False},
            },
        },
    )
    assert updated.status_code == 200
    body = updated.json()["user"]
    assert body["full_name"] == "Dev Atualizado"
    assert body["module_permissions"]["budget"]["hidden"] is True
