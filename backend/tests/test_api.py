"""Testes da API FastAPI."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("DB_ENABLED", "false")


@pytest.fixture
def client(monkeypatch):
    """Cliente com auth desligado — foco em lógica de rota, não em JWT."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("DB_ENABLED", "false")

    from config.settings import reload_settings

    reload_settings()

    from app.main import app

    return TestClient(app)


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "IA Server Santos"


def test_health(client):
    with patch("app.services.health_service.requests.get") as mock_get:
        mock_get.return_value.ok = True
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "database" in body
    assert body["rag_version"] == 2


@patch.object(
    __import__("models.ollama_client", fromlist=["OllamaClient"]).OllamaClient,
    "generate",
    return_value=("Resposta técnica LLM", "qwen3:14b"),
)
def test_chat(mock_generate, client):
    response = client.post(
        "/chat",
        json={"text": "dimensionar viga de concreto", "use_rag": False, "persist": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["discipline"] == "ESTRUTURAL"
    assert body["result"]
    assert body.get("intent", {}).get("mode") == "engineering_only"


@patch.object(
    __import__("models.ollama_client", fromlist=["OllamaClient"]).OllamaClient,
    "generate",
    return_value=("Relatório técnico LLM", "qwen3:14b"),
)
@patch("core.orchestrator.decompose_problem")
def test_orchestrate(mock_decompose, mock_generate, client):
    mock_decompose.return_value = ["ESTRUTURAL", "HIDROSSANITÁRIO", "INCÊNDIO", "ORÇAMENTO"]
    response = client.post(
        "/orchestrate",
        json={
            "text": "projeto de prédio residencial com estrutura e hidráulica",
            "use_rag": False,
            "persist": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["disciplines"]) >= 2
    assert body["final_report"]


def test_history(client):
    response = client.get("/history?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert "total" in body
    assert "items" in body
