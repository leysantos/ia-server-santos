"""Testes da API FastAPI."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "IA Server Santos"


def test_health():
    with patch("app.services.health_service.requests.get") as mock_get:
        mock_get.return_value.ok = True
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "database" in body
    assert body["rag_version"] == 2


@patch("app.services.chat_service.route")
def test_chat(mock_route):
    mock_route.return_value = {
        "input": "dimensionar viga de concreto",
        "discipline": "ESTRUTURAL",
        "agent": "estrutural_agent",
    }
    response = client.post(
        "/chat",
        json={"text": "dimensionar viga de concreto", "use_rag": False, "persist": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["discipline"] == "ESTRUTURAL"
    assert body["result"]


@patch("core.orchestrator.decompose_problem")
def test_orchestrate(mock_decompose):
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


def test_history():
    response = client.get("/history?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert "total" in body
    assert "items" in body


if __name__ == "__main__":
    test_root()
    test_health()
    test_chat()
    test_orchestrate()
    test_history()
    print("OK: testes API passaram")
