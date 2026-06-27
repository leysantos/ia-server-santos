"""Isolamento de conversas por usuário autenticado."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "true")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
os.environ.setdefault("DB_ENABLED", "false")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'conv_scope.db'}")

    from config.settings import reload_settings

    reload_settings()

    from core.database.connection import engine, init_db

    init_db()

    from app.main import app

    return TestClient(app)


def test_conversations_isolated_between_users(client):
    admin_token = _login(client, "admin", "Admin@2026!")
    dev_token = _login(client, "dev_user1", "Dev@2026!")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    r_admin = client.post(
        "/chat",
        headers=admin_headers,
        json={"text": "conversa exclusiva admin", "persist": True, "use_rag": False},
    )
    assert r_admin.status_code == 200, r_admin.text
    admin_conv_id = r_admin.json().get("conversation_id")
    assert admin_conv_id

    r_dev_list = client.get("/conversations", headers=dev_headers)
    assert r_dev_list.status_code == 200
    dev_ids = {c["id"] for c in r_dev_list.json()["items"]}
    assert admin_conv_id not in dev_ids

    r_dev_get = client.get(f"/conversations/{admin_conv_id}", headers=dev_headers)
    assert r_dev_get.status_code == 404

    r_dev_chat = client.post(
        "/chat",
        headers=dev_headers,
        json={
            "text": "tentativa hijack",
            "persist": True,
            "use_rag": False,
            "conversation_id": admin_conv_id,
        },
    )
    assert r_dev_chat.status_code == 404


def test_each_user_sees_only_own_conversations(client):
    admin_token = _login(client, "admin", "Admin@2026!")
    dev_token = _login(client, "dev_user2", "Dev@2026!")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    r1 = client.post(
        "/chat",
        headers=admin_headers,
        json={"text": "admin thread", "persist": True, "use_rag": False},
    )
    r2 = client.post(
        "/chat",
        headers=dev_headers,
        json={"text": "dev thread", "persist": True, "use_rag": False},
    )
    assert r1.status_code == 200 and r2.status_code == 200

    admin_conv = r1.json()["conversation_id"]
    dev_conv = r2.json()["conversation_id"]

    admin_list = client.get("/conversations", headers=admin_headers).json()["items"]
    dev_list = client.get("/conversations", headers=dev_headers).json()["items"]

    assert admin_conv in {c["id"] for c in admin_list}
    assert dev_conv in {c["id"] for c in dev_list}
    assert admin_conv not in {c["id"] for c in dev_list}
    assert dev_conv not in {c["id"] for c in admin_list}
