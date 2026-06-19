"""Operações administrativas sobre documentos do catálogo (editar / excluir)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.knowledge.catalog import append_catalog_entry, read_catalog, remove_catalog_entries_by_id
from core.knowledge.constants import KNOWLEDGE_INDEX_NAMES
from core.knowledge.content_types import normalize_content_type
from core.knowledge.disciplines import slug_for_discipline
from core.knowledge.metadata import read_metadata, sidecar_path, write_metadata
from core.knowledge.multi_index_store import get_multi_index_store
from core.knowledge.price_registry import clear_active_price_document, get_active_price_document_id, price_items_path
from pricing.budget.budget_model_extractor import budget_model_sidecar_path


def _find_catalog_entry(document_id: str) -> dict[str, Any]:
    rows = read_catalog()
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = row.get("id")
        if not rid:
            continue
        existing = by_id.get(rid)
        if not existing or (row.get("catalog_ts") or "") >= (existing.get("catalog_ts") or ""):
            by_id[rid] = row
    entry = by_id.get(document_id)
    if not entry:
        raise ValueError("Documento não encontrado no catálogo")
    return entry


def _remove_from_faiss_indices(doc_path: Path) -> int:
    if not doc_path.name:
        return 0
    file_key = str(doc_path.resolve())
    total = 0
    store_mgr = get_multi_index_store()
    for base_key in KNOWLEDGE_INDEX_NAMES:
        try:
            total += store_mgr.get_store(base_key).remove_by_path(file_key)
        except KeyError:
            continue
    return total


def _delete_sidecars_and_file(doc_path: Path) -> list[str]:
    removed: list[str] = []
    candidates = [
        doc_path,
        sidecar_path(doc_path),
        price_items_path(doc_path),
        budget_model_sidecar_path(doc_path),
    ]
    for path in candidates:
        if path.is_file():
            path.unlink()
            removed.append(str(path))
    return removed


def delete_document(document_id: str) -> dict[str, Any]:
    entry = _find_catalog_entry(document_id)
    doc_path = Path(entry.get("path", ""))
    was_active_price = get_active_price_document_id() == document_id

    faiss_removed = 0
    if doc_path.name:
        faiss_removed = _remove_from_faiss_indices(doc_path)

    files_removed = _delete_sidecars_and_file(doc_path) if doc_path.name else []
    catalog_removed = remove_catalog_entries_by_id(document_id)

    if was_active_price:
        clear_active_price_document()

    get_multi_index_store().reload_from_disk()

    return {
        "deleted": document_id,
        "filename": entry.get("filename") or doc_path.name,
        "was_active_price_base": was_active_price,
        "catalog_entries_removed": catalog_removed,
        "faiss_chunks_removed": faiss_removed,
        "files_removed": files_removed,
    }


def update_document_metadata(
    document_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    content_type: str | None = None,
    discipline: str | None = None,
) -> dict[str, Any]:
    entry = _find_catalog_entry(document_id)
    doc_path = Path(entry.get("path", ""))
    if not doc_path.is_file():
        raise ValueError(f"Arquivo não encontrado no disco: {doc_path.name or document_id}")

    meta = read_metadata(doc_path) or {}
    meta["id"] = document_id

    if name is not None:
        meta["name"] = name.strip()
    if description is not None:
        meta["description"] = description.strip()
    if content_type:
        ct = normalize_content_type(content_type)
        meta["content_type"] = ct
    if discipline:
        slug = slug_for_discipline(discipline)
        meta["discipline"] = [slug]
        meta["discipline_slug"] = slug
        meta["discipline_slugs"] = [slug]

    write_metadata(doc_path, meta)

    catalog_record = {
        **entry,
        "id": document_id,
        "name": meta.get("name") or entry.get("name"),
        "description": meta.get("description", ""),
        "filename": entry.get("filename") or doc_path.name,
        "path": str(doc_path.resolve()),
        "discipline": meta.get("discipline") or entry.get("discipline") or [],
        "content_type": meta.get("content_type") or entry.get("content_type", ""),
        "content_hash": entry.get("content_hash"),
        "price_item_count": entry.get("price_item_count", 0),
        "has_price_items": entry.get("has_price_items", False),
        "has_budget_model": entry.get("has_budget_model", False),
        "service_count": entry.get("service_count", 0),
    }
    append_catalog_entry(catalog_record)

    return {
        "updated": document_id,
        "name": catalog_record["name"],
        "description": catalog_record["description"],
        "content_type": catalog_record["content_type"],
        "discipline": catalog_record["discipline"],
        "filename": catalog_record["filename"],
    }
