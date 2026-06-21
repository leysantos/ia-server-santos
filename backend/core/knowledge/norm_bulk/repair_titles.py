"""Repara nomes genéricos (ex.: «NBR 6118») no catálogo a partir do arquivo/PDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.knowledge.document_admin import update_document_metadata
from core.knowledge.metadata import read_metadata
from core.knowledge.norm_bulk.title_extract import (
    extract_norm_display_name,
    is_bare_norm_name,
)
from memory.nbr_catalog import parse_nbr_code

logger = logging.getLogger(__name__)


def repair_bare_norm_catalog_names(
    rows: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    updated: list[dict[str, str]] = []
    skipped = 0
    errors: list[dict[str, str]] = []

    for row in rows:
        content_type = str(row.get("content_type") or "")
        if content_type not in ("nbrs", "nbr"):
            continue

        doc_id = row.get("id")
        path = Path(str(row.get("path") or ""))
        if not doc_id or not path.is_file():
            skipped += 1
            continue

        meta = read_metadata(path) or {}
        current_name = str(
            meta.get("norm_display_name")
            or meta.get("name")
            or row.get("name")
            or ""
        ).strip()
        norm_kind = str(meta.get("norm_kind") or "NBR").upper()
        norm_code = (
            meta.get("nbr_code")
            or meta.get("norm_code")
            or meta.get("nbr")
            or parse_nbr_code(path.name)
        )
        norm_code_str = str(norm_code) if norm_code else None

        if not is_bare_norm_name(current_name, norm_code_str) and meta.get("norm_display_name"):
            skipped += 1
            continue
        if not is_bare_norm_name(current_name, norm_code_str) and " - " in current_name:
            skipped += 1
            continue

        display = extract_norm_display_name(
            path,
            norm_kind=norm_kind if norm_kind in ("NBR", "NR") else "NBR",
            norm_code=norm_code_str,
        )
        if not display or display == current_name or is_bare_norm_name(display, norm_code_str):
            skipped += 1
            continue

        title = display.split(" - ", 1)[1].strip() if " - " in display else display
        if dry_run:
            updated.append(
                {
                    "id": doc_id,
                    "from": current_name,
                    "to": display,
                    "filename": path.name,
                }
            )
            continue

        try:
            update_document_metadata(
                doc_id,
                name=display,
                description=title,
            )
            sidecar = read_metadata(path) or {}
            sidecar["norm_display_name"] = display
            if title:
                sidecar["norm_title"] = title
            from core.knowledge.metadata import write_metadata

            write_metadata(path, sidecar)
            updated.append({"id": doc_id, "from": current_name, "to": display, "filename": path.name})
        except Exception as exc:
            logger.exception("Falha ao reparar título de %s", path.name)
            errors.append({"id": doc_id, "filename": path.name, "error": str(exc)})

    return {
        "dry_run": dry_run,
        "updated": len(updated),
        "skipped": skipped,
        "errors": errors,
        "documents": updated[:100],
    }
