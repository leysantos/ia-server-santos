"""Tests for knowledge maintenance helpers."""

from __future__ import annotations

from pathlib import Path

from core.knowledge.catalog_maintenance import list_orphan_catalog_entries, purge_orphan_catalog_entries
from core.knowledge.faiss_maintenance import compact_faiss_store
from core.knowledge.pdf_text_extractor import extract_pdf_pages
from memory.models import DocumentChunk


def test_extract_pdf_pages_empty_file(tmp_path: Path):
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"")
    assert extract_pdf_pages(pdf) == []


def test_compact_faiss_store_removes_orphan_metadata():
    class FakeStore:
        def __init__(self):
            self.chunks = [DocumentChunk(text="a"), DocumentChunk(text="b")]
            self.index = type("I", (), {"ntotal": 1})()
            self.saved = False

        def save(self):
            self.saved = True

    store = FakeStore()
    result = compact_faiss_store(store)
    assert result["removed"] == 1
    assert len(store.chunks) == 1
    assert store.saved


def test_list_orphan_catalog_entries(monkeypatch):
    monkeypatch.setattr(
        "core.knowledge.catalog_maintenance.read_catalog",
        lambda **_: [
            {"id": "a1", "path": "/no/such/file.pdf", "filename": "x.pdf", "catalog_ts": "1"},
            {"id": "a2", "path": __file__, "filename": "ok.py", "catalog_ts": "2"},
        ],
    )
    orphans = list_orphan_catalog_entries()
    assert len(orphans) == 1
    assert orphans[0]["id"] == "a1"


def test_purge_orphan_dry_run(monkeypatch):
    monkeypatch.setattr(
        "core.knowledge.catalog_maintenance.list_orphan_catalog_entries",
        lambda: [{"id": "x", "filename": "tmp.pdf"}],
    )
    result = purge_orphan_catalog_entries(dry_run=True)
    assert result["count"] == 1
