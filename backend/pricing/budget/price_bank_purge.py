"""Limpeza de banco de preços SINAPI (price_bank + artefatos de sync + FAISS legado)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from config.settings import KNOWLEDGE_DIR
from pricing.budget.price_bank_index import PRICE_BANK_ROOT, PriceBankIndex

REF_PATTERN = re.compile(r"BR-\d{4}-\d{2}", re.I)

PRICE_CONTENT_TYPES = frozenset({"sinapi", "tcpo", "bases_precos", "orse", "cicro"})


def infer_reference_from_catalog_entry(entry: dict[str, Any]) -> str | None:
    """Extrai BR-YYYY-MM de filename/nome/descrição de documento SINAPI no catálogo."""
    for field in ("filename", "name", "description", "path"):
        text = str(entry.get(field) or "")
        normalized = text.replace("/", "-")
        m = REF_PATTERN.search(normalized)
        if m:
            return m.group(0).upper()
        m2 = re.search(r"SINAPI-(\d{4})-(\d{2})", normalized, re.I)
        if m2:
            return f"BR-{m2.group(1)}-{m2.group(2)}"
        m3 = re.search(r"sinapi_[A-Z]{2}_(\d{4})(\d{2})", normalized, re.I)
        if m3:
            return f"BR-{m3.group(1)}-{m3.group(2)}"
    return None


def _normalize_reference(reference: str | None) -> str | None:
    if not reference:
        return None
    ref = reference.replace("/", "-").strip().upper()
    if not ref.startswith("BR-"):
        ref = f"BR-{ref}"
    return ref


def _path_matches_reference(path: str, reference: str) -> bool:
    ref = _normalize_reference(reference) or ""
    compact = ref.replace("-", "")
    normalized = path.replace("/", "-").replace("_", "-").upper()
    return ref in normalized or compact in normalized.replace("-", "")


def _is_sinapi_faiss_chunk(metadata: dict[str, Any]) -> bool:
    path = str(metadata.get("path") or "").lower()
    content_type = str(metadata.get("content_type") or "").lower()
    base = str(metadata.get("knowledge_base") or "").lower()
    filename = str(metadata.get("filename") or "").lower()
    if content_type in PRICE_CONTENT_TYPES or base in ("sinapi", "tcpo"):
        return True
    markers = ("sinapi", "tcpo", "price_bases", "fechadas.csv", "insumos.csv", "sicro")
    return any(m in path or m in filename for m in markers)


def purge_sinapi_faiss_chunks(*, reference: str | None = None) -> dict[str, Any]:
    """
    Remove chunks legados do índice cost_index (RAG) gerados por sync SINAPI/TCPO.

    O orçamento usa price_bank + composition_index — não depende deste índice.
    """
    from core.knowledge.multi_index_store import get_multi_index_store

    ref = _normalize_reference(reference)
    store_mgr = get_multi_index_store()
    store = store_mgr.get_store("sinapi")

    def should_remove(metadata: dict[str, Any]) -> bool:
        if not _is_sinapi_faiss_chunk(metadata):
            return False
        if ref:
            path = str(metadata.get("path") or "")
            filename = str(metadata.get("filename") or "")
            return _path_matches_reference(path, ref) or _path_matches_reference(filename, ref)
        return True

    removed = store.remove_where(should_remove)
    store_mgr.reload_from_disk()
    return {
        "index": "cost_index",
        "reference": ref,
        "chunks_removed": removed,
        "remaining": store.count(),
    }


def delete_price_bank_reference(reference: str) -> dict[str, Any]:
    """Remove pasta BR-YYYY-MM, entrada no index.json, CSVs espelhados e FAISS legado."""
    reference = _normalize_reference(reference) or reference

    idx = PriceBankIndex.load()
    had_index = idx.delete_reference(reference)

    ref_dir = PRICE_BANK_ROOT / reference
    removed_dir = False
    if ref_dir.is_dir():
        shutil.rmtree(ref_dir)
        removed_dir = True

    sync_removed: list[str] = []
    sync_root = KNOWLEDGE_DIR / "sync" / "price_bases" / "sinapi"
    if sync_root.is_dir():
        for pattern in (f"sinapi_{reference}_*", f"*{reference}*fechadas.csv"):
            for path in sync_root.glob(pattern):
                if path.is_file():
                    path.unlink()
                    sync_removed.append(str(path))

    pricing_data = Path(__file__).resolve().parents[1] / "data" / "sinapi"
    if pricing_data.is_dir():
        for pattern in (f"*{reference}*", f"sinapi_{reference}_*"):
            for path in pricing_data.glob(pattern):
                if path.is_file():
                    path.unlink()
                    sync_removed.append(str(path))

    raw_docs = KNOWLEDGE_DIR / "raw" / "documents"
    if raw_docs.is_dir():
        for pattern in (f"*{reference}*", f"*sinapi*{reference.replace('-', '')}*"):
            for path in raw_docs.glob(pattern):
                if path.is_file() and "sinapi" in path.name.lower():
                    path.unlink()
                    sync_removed.append(str(path))

    faiss_purge = purge_sinapi_faiss_chunks(reference=reference)

    if not had_index and not removed_dir and faiss_purge["chunks_removed"] == 0:
        raise ValueError(f"Referência '{reference}' não encontrada no banco de preços")

    return {
        "reference": reference,
        "index_removed": had_index,
        "directory_removed": removed_dir,
        "sync_files_removed": sync_removed,
        "faiss_purge": faiss_purge,
    }


def purge_price_bank_for_catalog_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    content_type = str(entry.get("content_type") or "").lower()
    if content_type not in PRICE_CONTENT_TYPES:
        return None
    ref = infer_reference_from_catalog_entry(entry)
    faiss = purge_sinapi_faiss_chunks(reference=ref) if ref else purge_sinapi_faiss_chunks()
    if not ref:
        return {"faiss_purge": faiss}
    try:
        result = delete_price_bank_reference(ref)
        return result
    except ValueError:
        return {"faiss_purge": faiss, "reference": ref, "price_bank_missing": True}
