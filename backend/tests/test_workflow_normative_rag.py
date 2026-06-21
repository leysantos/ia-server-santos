"""Testes — RAG normativo desenho técnico (workflow)."""

from __future__ import annotations

from core.workflow.delivery.normative_context import (
    DRAWING_NBR_CATALOG,
    _missing_priority_nbrs,
)


def test_drawing_nbr_catalog_has_core_norms():
    assert "8196" in DRAWING_NBR_CATALOG
    assert "10126" in DRAWING_NBR_CATALOG
    assert "6492" in DRAWING_NBR_CATALOG


def test_missing_priority_nbrs():
    missing = _missing_priority_nbrs(["NBR 6492", "NBR 10126"])
    codes = [m for m in missing if "8196" in m or "10067" in m]
    assert len(codes) >= 1
