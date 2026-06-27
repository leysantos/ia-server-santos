"""R10 — Project RAG: upload → indexação FAISS → contexto no chat (sem Ollama real)."""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "true")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
os.environ.setdefault("DB_ENABLED", "false")

_UNIQUE_MARKER = "MARCO_RAG_E2E_VIGA_V1_30CM"
_MEMORIAL = f"Memorial descritivo do empreendimento\nViga estrutural — {_UNIQUE_MARKER}\nCarga 200 kN"


class _FakeEmbedder:
    """Vetor fixo — FAISS cosine retorna match perfeito query=documento."""

    _vec = [1.0] + [0.0] * 767

    def embed_document(self, _text: str) -> list[float]:
        return list(self._vec)

    def embed_query(self, _text: str) -> list[float]:
        return list(self._vec)

    def embed_batch(self, texts: list[str], task: str = "document") -> list[list[float]]:
        return [list(self._vec) for _ in texts]

    def warmup(self) -> None:
        return None


@pytest.fixture
def fake_embedder(monkeypatch):
    monkeypatch.setattr("memory.embeddings.NomicEmbedder", _FakeEmbedder)


@pytest.fixture
def isolated_projects_root(monkeypatch, tmp_path):
    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)

    import app.services.workspace_service as ws
    import core.project_rag.project_rag as pr

    monkeypatch.setattr(ws, "PROJECTS_DATA_DIR", projects_root)
    monkeypatch.setattr(pr, "_PROJECTS_ROOT", projects_root)
    return projects_root


@pytest.fixture
def rag_client(monkeypatch, tmp_path, fake_embedder, isolated_projects_root):
    db_path = tmp_path / "rag_e2e.db"
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-minimum-32-chars")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("USE_INTENT_LAYER", "false")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.database.connection as db_conn

    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db_conn, "DB_ENABLED", True)
    monkeypatch.setattr(db_conn, "engine", test_engine)
    monkeypatch.setattr(
        db_conn,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=test_engine),
    )

    from config.settings import reload_settings

    reload_settings()

    from core.database.connection import init_db

    init_db()

    from app.main import app

    return TestClient(app)


def _login(client: TestClient) -> str:
    r = client.post("/auth/login", json={"username": "admin", "password": "Admin@2026!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_index_txt_and_build_project_context(tmp_path, fake_embedder, isolated_projects_root):
    from core.project_rag.project_rag import (
        build_project_context,
        get_project_store,
        index_project_file,
    )

    project_id = "proj-unit"
    memorial = tmp_path / "memorial.txt"
    memorial.write_text(_MEMORIAL, encoding="utf-8")

    result = index_project_file(project_id, memorial, "memorial.txt", force=True)
    assert result["status"] == "indexed"
    assert result["chunks"] >= 1
    assert get_project_store(project_id).count() >= 1

    ctx = build_project_context(f"qual carga da viga {_UNIQUE_MARKER}", project_id)
    assert _UNIQUE_MARKER in ctx
    assert "CONTEXTO DO PROJETO" in ctx


def test_rag_engine_enriches_route_with_project_context(tmp_path, fake_embedder, isolated_projects_root):
    from core.project_rag.project_rag import index_project_file
    from memory.rag_engine import RAGEngine

    project_id = "proj-enrich"
    memorial = tmp_path / "memorial.txt"
    memorial.write_text(_MEMORIAL, encoding="utf-8")
    index_project_file(project_id, memorial, force=True)

    engine = RAGEngine(embedder=_FakeEmbedder())
    route = {
        "input": f"descreva a viga {_UNIQUE_MARKER}",
        "discipline": "ESTRUTURAL",
        "_project_id": project_id,
        "_use_rag": True,
    }
    enriched = engine.enrich_route_result(route)
    assert enriched.get("project_rag", {}).get("active") is True
    assert _UNIQUE_MARKER in (enriched.get("context") or "")


def test_api_project_rag_full_flow(rag_client):
    """Upload → reindex → busca → chat com project_id (fluxo R10 completo)."""
    token = _login(rag_client)
    headers = {"Authorization": f"Bearer {token}"}

    created = rag_client.post(
        "/projects",
        headers=headers,
        json={"name": "Obra RAG E2E", "description": "validação R10"},
    )
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]

    upload = rag_client.post(
        f"/projects/{project_id}/files",
        headers=headers,
        files={"files": ("memorial.txt", io.BytesIO(_MEMORIAL.encode()), "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    assert body["uploaded"] == 1
    assert body["files"][0]["filename"] == "memorial.txt"
    assert any(row.get("status") == "indexed" for row in body.get("indexing", []))

    detail = rag_client.get(f"/projects/{project_id}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["files"]) == 1

    reindex = rag_client.post(f"/projects/{project_id}/reindex", headers=headers)
    assert reindex.status_code == 200, reindex.text
    assert reindex.json().get("indexed", 0) >= 1

    search = rag_client.get(
        "/workspace/search",
        params={"q": "Obra RAG"},
        headers=headers,
    )
    assert search.status_code == 200
    names = [p["name"] for p in search.json()["projects"]]
    assert "Obra RAG E2E" in names

    formats = rag_client.get("/projects/formats", headers=headers)
    assert formats.status_code == 200
    exts = {f["ext"] for f in formats.json()["formats"]}
    assert {".pdf", ".docx", ".xlsx", ".ifc", ".dxf"}.issubset(exts)

    captured: dict = {}

    def _fake_dispatch(route_result, persist=True):
        captured["context"] = route_result.get("context") or ""
        captured["project_rag"] = route_result.get("project_rag")
        return {
            "result": "Resposta simulada",
            "discipline": route_result.get("discipline", "GERAL"),
            "agent": route_result.get("agent", "chat_agent"),
        }

    with patch("core.dispatcher.dispatch", side_effect=_fake_dispatch):
        chat = rag_client.post(
            "/chat",
            headers=headers,
            json={
                "text": f"qual memorial menciona {_UNIQUE_MARKER}?",
                "persist": False,
                "use_rag": True,
                "project_id": project_id,
            },
        )

    assert chat.status_code == 200, chat.text
    assert captured.get("project_rag", {}).get("active") is True
    assert _UNIQUE_MARKER in captured.get("context", "")
