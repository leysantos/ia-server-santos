"""Smoke E2E — auth, health e workspace (sem dependência de Ollama na LAN)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "true")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
os.environ.setdefault("DB_ENABLED", "false")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'smoke.db'}")

    from config.settings import reload_settings

    reload_settings()

    from core.database.connection import init_db

    init_db()

    from app.main import app

    return TestClient(app)


def test_smoke_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "status" in r.json()


def test_smoke_auth_login_and_me(client):
    login = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "admin"


def test_smoke_conversations_authenticated(client):
    login = client.post("/auth/login", json={"username": "dev_user1", "password": "Dev@2026!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/conversations", headers=headers)
    assert r.status_code == 200
    assert "items" in r.json()

    r_unauth = client.get("/conversations")
    assert r_unauth.status_code == 401


def test_smoke_workspace_search_authenticated(client):
    login = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    token = login.json()["access_token"]
    r = client.get(
        "/workspace/search",
        params={"q": "teste"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "conversations" in body and "projects" in body
