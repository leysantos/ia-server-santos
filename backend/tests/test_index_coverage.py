"""Tests for NBR FAISS index coverage stats."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.knowledge.index_coverage import compute_nbr_index_coverage
from core.knowledge.metadata import write_metadata
from memory.models import DocumentChunk


def test_compute_nbr_index_coverage_empty():
    result = compute_nbr_index_coverage([])
    assert result["catalog_codes"] == 0
    assert result["coverage_pct"] == 0.0


def test_compute_nbr_index_coverage_by_file_path(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "NBR 6118 - 2014 - Projeto.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    write_metadata(pdf, {"content_type": "nbrs", "nbr_code": "6118", "norm_kind": "NBR"})
    rows = [{"content_type": "nbrs", "path": str(pdf), "filename": pdf.name}]

    chunk = DocumentChunk(
        text="trecho",
        embedding=[0.1] * 4,
        source="NBR 6118",
        doc_type="nbr",
        metadata={"path": str(pdf.resolve()), "filename": pdf.name, "nbr_code": "6118"},
    )

    class FakeStore:
        chunks = [chunk]

        def count(self):
            return len(self.chunks)

    monkeypatch.setattr(
        "core.knowledge.index_coverage.get_multi_index_store",
        lambda: type("M", (), {"get_store": lambda _self, _k: FakeStore()})(),
    )

    result = compute_nbr_index_coverage(rows)
    assert result["indexed_files"] == 1
    assert result["files_on_disk"] == 1
    assert result["file_coverage_pct"] == 100.0
    assert result["faiss_chunks"] == 1
