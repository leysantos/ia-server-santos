"""Testes — carimbo auditoria IA."""

from __future__ import annotations

from core.workflow.publish.stamp_audit import build_stamp_audit, format_stamp_audit_lines


def test_stamp_audit_includes_model_and_nbrs():
    audit = build_stamp_audit(
        analysis_json={
            "ai_model": "qwen3:14b",
            "llm_refined": True,
            "normative_rag": {
                "rag_available": True,
                "hits_count": 4,
                "legal_filter": "abnt_licensed_pdf_only",
                "nbrs_cited": ["NBR 6492", "NBR 10126"],
            },
        },
        pipeline="workflow_wizard",
    )
    lines = format_stamp_audit_lines(audit)
    joined = "\n".join(lines)
    assert "qwen3:14b" in joined
    assert "NBR 6492" in joined
    assert "PDF lic." in joined
    assert "RAG: 4" in joined
    assert "LLM: sim" in joined
