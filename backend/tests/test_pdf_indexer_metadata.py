"""Tests for PDF indexer metadata fix."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from memory.models import DocumentChunk
from memory.pdf_indexer import PDFIndexer


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.is_indexed.return_value = False
    store.is_indexed_by_hash.return_value = False
    store.add_many.side_effect = lambda chunks: len(chunks)
    return store


def test_index_pdf_sets_nbr_code_in_metadata(tmp_path: Path, mock_store):
    pdf = tmp_path / "NBR 6118 - 2014 - Projeto.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")

    indexer = PDFIndexer(store=mock_store)
    with patch.object(indexer, "extract_text", return_value=[(1, "texto norma estrutural " * 20)]):
        with patch.object(indexer.embedder, "embed_document", return_value=[0.1] * 8):
            count = indexer.index_pdf(pdf, doc_type="nbr", force=True)

    assert count > 0
    chunks = mock_store.add_many.call_args[0][0]
    assert isinstance(chunks[0], DocumentChunk)
    assert chunks[0].metadata.get("nbr_code") == "6118"
    assert chunks[0].metadata.get("path") == str(pdf.resolve())
