"""Testes — editar e excluir documentos do catálogo."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.knowledge.catalog import (
    append_catalog_entry,
    read_catalog,
    remove_catalog_entries_by_id,
    rewrite_catalog,
)
from core.knowledge.document_admin import delete_document, update_document_metadata
from core.knowledge.metadata import write_metadata


def test_rewrite_and_remove_catalog_entries(tmp_path, monkeypatch):
    from core.knowledge import catalog as catalog_mod

    catalog_path = tmp_path / "catalog.jsonl"
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(catalog_mod, "KNOWLEDGE_DIR", tmp_path)

    append_catalog_entry({"id": "a", "filename": "a.pdf", "catalog_ts": "1"})
    append_catalog_entry({"id": "b", "filename": "b.pdf", "catalog_ts": "2"})
    append_catalog_entry({"id": "a", "filename": "a.pdf", "catalog_ts": "3"})

    assert remove_catalog_entries_by_id("a") == 2
    rows = read_catalog()
    assert len(rows) == 1
    assert rows[0]["id"] == "b"

    rewrite_catalog([{"id": "c", "filename": "c.pdf"}])
    assert read_catalog()[0]["id"] == "c"


def test_read_metadata_ignores_empty_sidecar(tmp_path):
    from core.knowledge.metadata import read_metadata, write_metadata

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    sidecar = pdf.with_name(pdf.name + ".knowledge.json")
    sidecar.write_text("", encoding="utf-8")

    assert read_metadata(pdf) is None

    write_metadata(pdf, {"id": "x", "content_type": "nbrs"})
    meta = read_metadata(pdf)
    assert meta is not None
    assert meta["content_type"] == "nbrs"


def test_read_catalog_skips_corrupt_lines(tmp_path, monkeypatch):
    from core.knowledge import catalog as catalog_mod

    catalog_path = tmp_path / "catalog.jsonl"
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(catalog_mod, "KNOWLEDGE_DIR", tmp_path)

    catalog_path.write_text(
        '{"id": "ok", "filename": "a.pdf"}\n'
        "\x00" * 40 + "\n"
        '{"id": "ok2", "filename": "b.pdf"}\n',
        encoding="utf-8",
    )

    rows = read_catalog(repair=True)
    assert len(rows) == 2
    assert rows[0]["id"] == "ok"
    assert rows[1]["id"] == "ok2"
    # arquivo reparado sem linha corrompida
    assert "\x00" not in catalog_path.read_text(encoding="utf-8")


def test_update_document_metadata(tmp_path, monkeypatch):
    from core.knowledge import catalog as catalog_mod

    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF test")
    write_metadata(doc, {"id": "doc-1", "name": "Original", "content_type": "nbrs"})

    catalog_path = tmp_path / "catalog.jsonl"
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(catalog_mod, "KNOWLEDGE_DIR", tmp_path)

    append_catalog_entry(
        {
            "id": "doc-1",
            "filename": doc.name,
            "path": str(doc.resolve()),
            "name": "Original",
            "content_type": "nbrs",
            "discipline": ["estruturas"],
            "catalog_ts": "1",
        }
    )

    result = update_document_metadata(
        "doc-1",
        name="NBR Atualizada",
        description="Nova descrição",
        content_type="manuais",
        discipline="GERAL",
    )

    assert result["name"] == "NBR Atualizada"
    assert result["description"] == "Nova descrição"
    assert result["content_type"] == "manuais"
    assert result["discipline"] == ["geral"]

    meta_path = doc.with_name(doc.name + ".knowledge.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["name"] == "NBR Atualizada"
    assert meta["description"] == "Nova descrição"


def test_delete_document_removes_files_and_catalog(tmp_path, monkeypatch):
    from core.knowledge import catalog as catalog_mod
    from core.knowledge import price_registry as price_mod

    doc = tmp_path / "sinapi.csv"
    doc.write_text("codigo,descricao\n1,item\n", encoding="utf-8")
    sidecar = doc.with_name(doc.name + ".knowledge.json")
    sidecar.write_text(json.dumps({"id": "price-1"}), encoding="utf-8")
    price_sidecar = doc.with_name(doc.name + ".price_items.json")
    price_sidecar.write_text("[]", encoding="utf-8")

    catalog_path = tmp_path / "catalog.jsonl"
    pricing_active = tmp_path / "pricing_active.json"
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(catalog_mod, "KNOWLEDGE_DIR", tmp_path)
    monkeypatch.setattr(price_mod, "PRICING_ACTIVE_PATH", pricing_active)
    pricing_active.write_text(json.dumps({"active_document_id": "price-1"}), encoding="utf-8")

    append_catalog_entry(
        {
            "id": "price-1",
            "filename": doc.name,
            "path": str(doc.resolve()),
            "name": "SINAPI",
            "content_type": "sinapi",
            "catalog_ts": "1",
        }
    )

    mock_store = MagicMock()
    mock_store.remove_by_path.return_value = 3
    mock_mgr = MagicMock()
    mock_mgr.get_store.return_value = mock_store
    mock_mgr.reload_from_disk = MagicMock()

    with patch("core.knowledge.document_admin.get_multi_index_store", return_value=mock_mgr):
        result = delete_document("price-1")

    assert result["deleted"] == "price-1"
    assert result["was_active_price_base"] is True
    assert result["catalog_entries_removed"] == 1
    assert not doc.exists()
    assert not sidecar.exists()
    assert not price_sidecar.exists()
    assert not pricing_active.exists()
    assert read_catalog() == []
