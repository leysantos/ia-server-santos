"""Registro de bases de preço vinculadas ao catálogo unificado de documentos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config.settings import KNOWLEDGE_DIR
from core.knowledge.catalog import read_catalog
from core.knowledge.metadata import read_metadata

PRICE_ITEMS_SUFFIX = ".price_items.json"
PRICING_ACTIVE_PATH = KNOWLEDGE_DIR / "pricing_active.json"
PRICE_CONTENT_TYPES = frozenset({"sinapi", "tcpo", "bases_precos"})


def price_items_path(document_path: Path) -> Path:
    return document_path.with_name(document_path.name + PRICE_ITEMS_SUFFIX)


def write_price_items(document_path: Path, rows: list[dict[str, Any]]) -> Path:
    path = price_items_path(document_path)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_price_items(document_path: Path) -> list[dict[str, Any]]:
    path = price_items_path(document_path)
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def parse_price_rows_from_file(path: Path) -> list[dict[str, Any]]:
    from pricing.budget.price_base_store import _parse_price_rows

    return _parse_price_rows(path, path.suffix.lower())


def set_active_price_document(document_id: str) -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    PRICING_ACTIVE_PATH.write_text(
        json.dumps({"active_document_id": document_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_active_price_document_id() -> str | None:
    if not PRICING_ACTIVE_PATH.is_file():
        return None
    data = json.loads(PRICING_ACTIVE_PATH.read_text(encoding="utf-8"))
    return data.get("active_document_id")


def clear_active_price_document() -> None:
    if PRICING_ACTIVE_PATH.is_file():
        PRICING_ACTIVE_PATH.unlink()


def _catalog_by_id() -> dict[str, dict[str, Any]]:
    rows = read_catalog()
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        doc_id = row.get("id")
        if doc_id:
            existing = by_id.get(doc_id)
            if not existing or (row.get("catalog_ts") or "") >= (existing.get("catalog_ts") or ""):
                by_id[doc_id] = row
    return by_id


def load_active_price_rows() -> tuple[str, list[dict[str, Any]], dict[str, Any]] | None:
    """Retorna (nome, rows, catalog_entry) da base de preço ativa no catálogo."""
    doc_id = get_active_price_document_id()
    if not doc_id:
        return None

    entry = _catalog_by_id().get(doc_id)
    if not entry:
        return None

    doc_path = Path(entry.get("path", ""))
    if not doc_path.is_file():
        return None

    cached = read_price_items(doc_path)
    fresh = parse_price_rows_from_file(doc_path)
    if fresh and len(fresh) > len(cached):
        write_price_items(doc_path, fresh)
        rows = fresh
    elif cached:
        rows = cached
    elif fresh:
        write_price_items(doc_path, fresh)
        rows = fresh
    else:
        rows = []

    if not rows:
        return None

    meta = read_metadata(doc_path) or {}
    name = meta.get("name") or entry.get("name") or doc_path.stem
    return name, rows, entry


def is_price_content_type(content_type: str) -> bool:
    return content_type in PRICE_CONTENT_TYPES
