"""Guard de runtime — retrieval index-first, sem I/O de PDF/arquivo."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

_active = threading.local()


def is_rag_query_active() -> bool:
    return bool(getattr(_active, "enabled", False))


@contextmanager
def rag_query_context() -> Iterator[None]:
    """Marca janela de query RAG — index-only, sem parsing de PDF."""
    prev = getattr(_active, "enabled", False)
    _active.enabled = True
    try:
        yield
    finally:
        _active.enabled = prev


def assert_index_only_path(path: str) -> None:
    """Levanta se código tenta abrir PDF durante query RAG."""
    if not is_rag_query_active():
        return
    lower = path.lower()
    blocked = (".pdf", "pypdf", "pdfreader", "extract_text")
    if any(b in lower for b in blocked):
        raise RuntimeError(
            f"Leitura de PDF proibida em runtime RAG: {path}. "
            "Use apenas índice FAISS + cache."
        )
