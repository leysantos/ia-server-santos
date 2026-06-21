"""Manutenção e rebuild de índices FAISS."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from core.knowledge.constants import KNOWLEDGE_INDEX_DIR, KNOWLEDGE_INDEX_NAMES
from core.knowledge.multi_index_store import get_multi_index_store
from memory.embeddings import NomicEmbedder
from memory.faiss_store import FaissVectorStore

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]


def compact_faiss_store(store: FaissVectorStore) -> dict[str, int]:
    """
    Remove chunks metadata órfãos (sem vetor no índice).
    Assume alinhamento posicional: vetor i ↔ chunk i.
    """
    before = len(store.chunks)
    ntotal = store.index.ntotal if store.index else 0
    if before <= ntotal:
        return {"before": before, "after": before, "removed": 0}

    store.chunks = store.chunks[:ntotal]
    store.save()
    return {"before": before, "after": len(store.chunks), "removed": before - ntotal}


def reembed_faiss_store(
    store: FaissVectorStore,
    embedder: Optional[NomicEmbedder] = None,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Re-embed todos os chunks a partir do texto e reconstrói o índice FAISS."""
    embedder = embedder or NomicEmbedder()
    total = len(store.chunks)
    if total == 0:
        store.clear()
        store.save()
        return {"chunks": 0, "reembedded": 0}

    reembedded = 0
    for idx, chunk in enumerate(store.chunks):
        if not (chunk.text or "").strip():
            continue
        chunk.embedding = embedder.embed_document(chunk.text)
        reembedded += 1
        if on_progress and (idx <= 1 or idx % 50 == 0 or idx + 1 == total):
            on_progress(
                {
                    "phase": "reembed",
                    "current": idx + 1,
                    "total": total,
                    "percent": round((idx + 1) / total * 100),
                    "message": f"Re-embed chunk {idx + 1}/{total}",
                }
            )

    store._rebuild_index()
    store.save()
    return {
        "chunks": total,
        "reembedded": reembedded,
        "faiss_vectors": store.index.ntotal if store.index else 0,
    }


def maintain_faiss_base(
    base_key: str,
    *,
    compact: bool = True,
    reembed: bool = False,
    embedder: Optional[NomicEmbedder] = None,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    store = get_multi_index_store().get_store(base_key)
    before_chunks = len(store.chunks)
    before_faiss = store.index.ntotal if store.index else 0

    compact_result: dict[str, int] = {"before": before_chunks, "after": before_chunks, "removed": 0}
    if compact:
        compact_result = compact_faiss_store(store)

    reembed_result: dict[str, Any] = {}
    if reembed:
        reembed_result = reembed_faiss_store(store, embedder, on_progress=on_progress)

    after_chunks = len(store.chunks)
    after_faiss = store.index.ntotal if store.index else 0

    return {
        "base": base_key,
        "index_dir": str(KNOWLEDGE_INDEX_DIR / KNOWLEDGE_INDEX_NAMES.get(base_key, base_key)),
        "before_chunks": before_chunks,
        "before_faiss": before_faiss,
        "after_chunks": after_chunks,
        "after_faiss": after_faiss,
        "compact": compact_result,
        "reembed": reembed_result,
    }


def maintain_all_faiss(
    *,
    compact: bool = True,
    reembed: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for base_key in KNOWLEDGE_INDEX_NAMES:
        results[base_key] = maintain_faiss_base(
            base_key,
            compact=compact,
            reembed=reembed,
            on_progress=on_progress,
        )
    get_multi_index_store().reload_from_disk()
    return results
