"""Testes — filtro legal no carimbo e RAG normativo."""

from __future__ import annotations

from core.knowledge.norm_packs.legal import (
    NormLegalSource,
    is_stamp_eligible,
    resolve_legal_source,
)
from core.workflow.delivery.normative_context import retrieve_drawing_normative_context
from core.workflow.publish.stamp_audit import build_stamp_audit, format_stamp_audit_lines
from unittest.mock import MagicMock, patch


def test_is_stamp_eligible_only_abnt_licensed():
    assert is_stamp_eligible(NormLegalSource.ABNT_LICENSED_PDF)
    assert not is_stamp_eligible(NormLegalSource.PUBLIC_LEGISLATION)
    assert not is_stamp_eligible(NormLegalSource.UNKNOWN)
    assert not is_stamp_eligible(None)


def test_resolve_legal_source_from_meta():
    src = resolve_legal_source({"legal_source": "abnt_licensed_pdf", "content_type": "nbrs"})
    assert src == NormLegalSource.ABNT_LICENSED_PDF


def test_resolve_legal_source_nbr_doc_type_fallback():
    src = resolve_legal_source({}, doc_type="nbr")
    assert src == NormLegalSource.ABNT_LICENSED_PDF


def test_stamp_audit_filters_unlicensed_sources():
    audit = build_stamp_audit(
        analysis_json={
            "ai_model": "qwen3:14b",
            "llm_refined": True,
            "normative_rag": {
                "rag_available": True,
                "hits_count": 1,
                "hits_total": 2,
                "hits_excluded_unlicensed": 1,
                "legal_filter": "abnt_licensed_pdf_only",
                "nbrs_cited": ["NBR 6492"],
                "sources": [
                    {
                        "norma": "NBR 6492",
                        "legal_source": "abnt_licensed_pdf",
                        "stamp_eligible": True,
                    },
                    {
                        "norma": "Decreto 46366",
                        "legal_source": "public_legislation",
                        "stamp_eligible": False,
                    },
                ],
            },
        },
        pipeline="workflow_wizard",
    )
    lines = format_stamp_audit_lines(audit)
    joined = "\n".join(lines)
    assert audit["nbrs_consultadas"] == ["NBR 6492"]
    assert audit["nbrs_excluded_unlicensed"] == 1
    assert "PDF lic." in joined
    assert "6492" in joined
    assert "46366" not in joined
    assert "1 excl." in joined


def test_stamp_audit_no_licensed_nbrs():
    audit = build_stamp_audit(
        analysis_json={
            "normative_rag": {
                "rag_available": False,
                "hits_count": 0,
                "hits_excluded_unlicensed": 2,
                "nbrs_cited": [],
            },
        }
    )
    lines = format_stamp_audit_lines(audit)
    assert "sem PDF licenciado" in "\n".join(lines)


def test_normative_context_excludes_non_licensed_hits():
    chunk_lic = MagicMock()
    chunk_lic.metadata = {"norma": "NBR 6492", "filename": "NBR 6492.pdf", "legal_source": "abnt_licensed_pdf"}
    chunk_lic.doc_type = "nbr"
    chunk_lic.text = "Representação de plantas conforme norma."
    chunk_lic.source = "NBR 6492"

    chunk_pub = MagicMock()
    chunk_pub.metadata = {"filename": "decreto.pdf", "legal_source": "public_legislation", "content_type": "regional"}
    chunk_pub.doc_type = "regional"
    chunk_pub.text = "Decreto municipal PCI."
    chunk_pub.source = "Decreto"

    result_mock = MagicMock()
    result_mock.hits = [(chunk_lic, 0.9), (chunk_pub, 0.85)]
    result_mock.bases_used = ["nbr"]

    with patch("core.knowledge.rag.agent_retriever.retrieve_for_agent", return_value=result_mock):
        normative = retrieve_drawing_normative_context(disciplina="arquitetura", role="prancha", top_k=6)

    assert normative["hits_count"] == 1
    assert normative["hits_excluded_unlicensed"] == 1
    assert normative["nbrs_cited"] == ["NBR 6492"]
    assert all(s.get("stamp_eligible") for s in normative["sources"])
