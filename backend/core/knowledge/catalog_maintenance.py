"""Manutenção do catálogo e metadata de normas."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.knowledge.catalog import append_catalog_entry, read_catalog, rewrite_catalog
from core.knowledge.metadata import read_metadata, write_metadata
from core.knowledge.document_admin import delete_document
from core.knowledge.disciplines import slug_for_discipline
from memory.nbr_catalog import infer_discipline, normalize_nbr_code, parse_nbr_code

logger = logging.getLogger(__name__)

_PRIORITY_NORM_CODES = ("9077", "14833")


def _latest_catalog_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = row.get("id")
        if not rid:
            continue
        existing = by_id.get(rid)
        if not existing or (row.get("catalog_ts") or "") >= (existing.get("catalog_ts") or ""):
            by_id[rid] = row
    return by_id


def list_orphan_catalog_entries() -> list[dict[str, Any]]:
    """Entradas cujo path não existe mais no disco."""
    by_id = _latest_catalog_by_id(read_catalog())
    orphans: list[dict[str, Any]] = []
    for doc_id, row in by_id.items():
        path = Path(str(row.get("path") or ""))
        if not path.is_file():
            orphans.append({**row, "id": doc_id})
    return sorted(orphans, key=lambda r: str(r.get("filename") or ""))


def purge_orphan_catalog_entries(*, dry_run: bool = False) -> dict[str, Any]:
    """Remove do catálogo entradas sem arquivo (ex.: tmp*.pdf de importação)."""
    orphans = list_orphan_catalog_entries()
    if dry_run:
        return {
            "dry_run": True,
            "count": len(orphans),
            "documents": [
                {
                    "id": o.get("id"),
                    "filename": o.get("filename"),
                    "path": o.get("path"),
                }
                for o in orphans
            ],
        }

    removed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for row in orphans:
        doc_id = str(row.get("id") or "")
        if not doc_id:
            continue
        try:
            removed.append(delete_document(doc_id))
        except ValueError as exc:
            errors.append({"id": doc_id, "error": str(exc)})

    return {
        "dry_run": False,
        "requested": len(orphans),
        "removed": len(removed),
        "errors": errors,
        "documents": removed,
    }


def repair_priority_norm_sidecars(
    documents_dir: Path,
    *,
    codes: tuple[str, ...] = _PRIORITY_NORM_CODES,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Garante nbr_code/discipline nos sidecars de normas prioritárias (9077, 14833…).
    """
    documents_dir = Path(documents_dir)
    repaired: list[dict[str, Any]] = []
    skipped: list[str] = []

    for pdf_path in sorted(documents_dir.glob("*.pdf")):
        code = normalize_nbr_code(parse_nbr_code(pdf_path.name))
        if not code or code not in codes:
            continue

        meta = read_metadata(pdf_path) or {}
        changed = False
        mapped = infer_discipline(code)
        discipline_slug = slug_for_discipline(mapped) if mapped else "geral"

        if meta.get("nbr_code") != code:
            meta["nbr_code"] = code
            meta["norm_code"] = code
            changed = True
        if meta.get("content_type") not in ("nbrs", "nbr"):
            meta["content_type"] = "nbrs"
            changed = True
        if code and not meta.get("norm_kind"):
            meta["norm_kind"] = "NBR"
            changed = True
        if discipline_slug and meta.get("discipline_slug") != discipline_slug:
            meta["discipline"] = [discipline_slug]
            meta["discipline_slug"] = discipline_slug
            meta["discipline_slugs"] = [discipline_slug]
            changed = True

        if not changed:
            skipped.append(pdf_path.name)
            continue

        if dry_run:
            repaired.append({"file": pdf_path.name, "nbr_code": code, "would_update": True})
            continue

        write_metadata(pdf_path, meta)
        append_catalog_entry(
            {
                "id": meta.get("id"),
                "name": meta.get("name") or pdf_path.stem,
                "filename": pdf_path.name,
                "path": str(pdf_path.resolve()),
                "content_type": meta.get("content_type", "nbrs"),
                "discipline": meta.get("discipline", [discipline_slug]),
                "content_hash": meta.get("content_hash"),
            }
        )
        repaired.append({"file": pdf_path.name, "nbr_code": code, "updated": True})

    return {
        "dry_run": dry_run,
        "codes": list(codes),
        "repaired": len(repaired),
        "skipped": len(skipped),
        "files": repaired,
    }


def dedupe_catalog_by_path(*, dry_run: bool = False) -> dict[str, Any]:
    """Mantém só a entrada mais recente por path absoluto."""
    rows = read_catalog()
    best_by_path: dict[str, dict[str, Any]] = {}
    for row in rows:
        path = str(row.get("path") or "")
        if not path:
            continue
        existing = best_by_path.get(path)
        if not existing or (row.get("catalog_ts") or "") >= (existing.get("catalog_ts") or ""):
            best_by_path[path] = row

    kept = list(best_by_path.values())
    removed = len(rows) - len(kept)
    if not dry_run and removed:
        rewrite_catalog(kept)

    return {"dry_run": dry_run, "before": len(rows), "after": len(kept), "removed": removed}
