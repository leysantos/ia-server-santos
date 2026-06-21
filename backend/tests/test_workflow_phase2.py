"""Testes — Workflow Fase 2 (PDF, storage, dispatcher)."""

from __future__ import annotations

from core.workflow.publish.pdf_generator import generate_publication_pdf, generate_sheet_pdf
from core.workflow.storage.paths import build_storage_key, sanitize_segment


def test_storage_key_structure():
    key = build_storage_key(
        tenant="empresa-1",
        project_id="abc-123",
        discipline="estrutural",
        revision="REV01",
        version="deadbeef",
        filename="publicacao.pdf",
    )
    parts = key.split("/")
    assert len(parts) == 6
    assert parts[-1] == "publicacao.pdf"
    assert parts[2] == "estrutural"
    assert parts[3] == "REV01"


def test_sanitize_segment():
    assert sanitize_segment("Hidro/Sanitário") == "Hidro_Sanitário"
    assert sanitize_segment("") == "geral"


def test_generate_sheet_pdf_with_stamp_audit():
    from core.workflow.publish.stamp_audit import build_stamp_audit

    audit = build_stamp_audit(
        analysis_json={
            "ai_model": "qwen3:14b",
            "llm_refined": True,
            "normative_rag": {
                "rag_available": True,
                "hits_count": 5,
                "nbrs_cited": ["NBR 6492", "NBR 10126", "NBR 8196"],
            },
            "observacao_normativa": "Escala conforme NBR 6492",
        },
        pipeline="workflow_wizard",
    )
    data = generate_sheet_pdf(
        {
            "formato": "A4",
            "orientacao": "retrato",
            "titulo": "Planta Baixa",
            "escala": "1:50",
            "empresa": "Santos Eng",
            "revisao": "REV00",
            "stamp_audit": audit,
        }
    )
    assert data[:4] == b"%PDF"
    assert len(data) > 600


def test_generate_sheet_pdf_bytes():
    data = generate_sheet_pdf(
        {
            "formato": "A4",
            "orientacao": "retrato",
            "titulo": "Planta Baixa",
            "escala": "1:50",
            "empresa": "Santos Eng",
            "revisao": "REV00",
        }
    )
    assert data[:4] == b"%PDF"
    assert len(data) > 500


def test_generate_publication_pdf_bytes():
    data = generate_publication_pdf(
        {"project_name": "Escola Metamorfose", "revisao": "REV01", "cliente": "Cliente X"},
        sheets=[{"numero_prancha": "01", "codigo_desenho": "ARQ-01", "escala": "1:100"}],
    )
    assert data[:4] == b"%PDF"


def test_redis_available_false_on_invalid():
    from core.workflow.workers.dispatcher import _redis_available

    assert _redis_available("redis://127.0.0.1:59999/0") is False
