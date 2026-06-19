"""
Legacy Guard — data/ read-only; writes only under backend/knowledge/.
"""

from __future__ import annotations

from pathlib import Path

from core.knowledge.resolver import is_discipline_path, is_legacy_path


def assert_legacy_kb_write_allowed(context: str = "write") -> None:
    """No-op — knowledge_base/ removido."""


def assert_ingest_target(path: Path) -> None:
    if is_legacy_path(path):
        raise PermissionError(
            f"Escrita proibida em data/ legado: {path}. "
            "Use knowledge/raw/documents/."
        )
    if not is_discipline_path(path):
        raise PermissionError(
            f"Escrita permitida apenas em backend/knowledge/: {path}"
        )


def allowed_ingest_layer(layer: str = "raw") -> str:
    if layer not in ("raw", "canonical", "structured", "embeddings"):
        raise ValueError(f"Layer inválida para ingestão: {layer}")
    return layer
