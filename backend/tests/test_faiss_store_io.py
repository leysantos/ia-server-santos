"""Testes — persistência segura do índice FAISS."""

import json
import threading
from pathlib import Path
from unittest.mock import patch

from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk


def test_save_uses_atomic_replace(tmp_path: Path):
    index_dir = tmp_path / "idx"
    store = FaissVectorStore(index_dir=index_dir)
    store.add(
        DocumentChunk(
            text="norma sicro",
            embedding=[1.0, 0.0, 0.0],
            discipline="ORÇAMENTO",
            doc_type="nbr",
        )
    )
    store.save()

    assert (index_dir / "chunks.json").is_file()
    assert (index_dir / "index.faiss").is_file()
    assert not (index_dir / "chunks.json.tmp").exists()

    reloaded = FaissVectorStore(index_dir=index_dir)
    assert reloaded.count() == 1


def test_load_falls_back_to_backup_on_corrupt_primary(tmp_path: Path):
    index_dir = tmp_path / "idx"
    store = FaissVectorStore(index_dir=index_dir)
    store.add(
        DocumentChunk(
            text="backup ok",
            embedding=[0.0, 1.0, 0.0],
            discipline="ORÇAMENTO",
            doc_type="nbr",
        )
    )
    store.save()
    store.save()  # segunda gravação cria chunks.json.bak

    backup = index_dir / "chunks.json.bak"
    assert backup.is_file()

    (index_dir / "chunks.json").write_text("{invalid json", encoding="utf-8")

    recovered = FaissVectorStore(index_dir=index_dir)
    assert recovered.count() == 1
    assert recovered.chunks[0].text == "backup ok"


def test_reload_if_changed_skips_when_mtime_unchanged(tmp_path: Path):
    index_dir = tmp_path / "idx"
    store = FaissVectorStore(index_dir=index_dir)
    store.add(
        DocumentChunk(
            text="a",
            embedding=[1.0, 0.0, 0.0],
            doc_type="nbr",
        )
    )
    store.save()

    with patch.object(store, "reload") as reload_mock:
        assert store.reload_if_changed() is False
        reload_mock.assert_not_called()


def test_concurrent_save_and_reload_does_not_raise(tmp_path: Path):
    index_dir = tmp_path / "idx"
    store = FaissVectorStore(index_dir=index_dir)

    errors: list[Exception] = []

    def writer() -> None:
        try:
            for i in range(5):
                store.add(
                    DocumentChunk(
                        text=f"chunk {i}",
                        embedding=[1.0, float(i) * 0.01, 0.0],
                        doc_type="nbr",
                    )
                )
                store.save()
        except Exception as exc:
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(10):
                store.reload_if_changed()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    payload = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
    assert payload["count"] == 5
