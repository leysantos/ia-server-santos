from __future__ import annotations

import logging
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from fastapi import UploadFile

from core.agent_registry import DISCIPLINE_TO_AGENT
from core.knowledge.catalog import read_catalog
from core.knowledge.content_types import (
    CONTENT_TYPE_TO_BASE_KEY,
    KNOWLEDGE_CONTENT_TYPES,
    normalize_content_type,
)
from core.knowledge.constants import KNOWLEDGE_PATHS
from core.knowledge.ingestion import INGESTABLE_SUFFIXES, get_ingester
from core.knowledge.knowledge_base_router import get_knowledge_router
from core.knowledge.knowledge_indexer import KnowledgeIndexer
from core.knowledge.multi_index_store import get_multi_index_store

logger = logging.getLogger(__name__)

_CONTENT_TYPE_LABELS: dict[str, str] = {
    "nbrs": "NBR (Normas técnicas)",
    "sinapi": "SINAPI (Composições de custo)",
    "tcpo": "TCPO (Orçamento)",
    "tdrs": "TDR / Termos de referência",
    "catalogos": "Catálogos",
    "manuais": "Manuais",
    "projetos": "Projetos",
    "regional": "Dados regionais",
}

_BASE_LABELS: dict[str, str] = {
    "nbr": "NBR",
    "sinapi": "SINAPI",
    "tcpo": "TCPO",
    "tdr": "TDR",
    "catalogos": "Catálogos",
    "regional": "Regional",
}


def _dedupe_catalog_rows(rows: list[dict]) -> list[dict]:
    """Um registro por arquivo (path), mantendo a ingestão mais recente."""
    by_path: dict[str, dict] = {}
    for row in rows:
        key = row.get("path") or row.get("filename") or row.get("id", "")
        if not key:
            continue
        existing = by_path.get(key)
        if not existing or (row.get("catalog_ts") or "") >= (existing.get("catalog_ts") or ""):
            by_path[key] = row
    return sorted(
        by_path.values(),
        key=lambda r: r.get("catalog_ts") or "",
        reverse=True,
    )


class KnowledgeService:
    def get_options(self) -> dict[str, Any]:
        disciplines = [
            {"value": key, "label": key.replace("_", " ").title()}
            for key in DISCIPLINE_TO_AGENT
        ]
        content_types = [
            {"value": ct, "label": _CONTENT_TYPE_LABELS.get(ct, ct.upper())}
            for ct in KNOWLEDGE_CONTENT_TYPES
        ]
        bases = [
            {"value": base, "label": _BASE_LABELS.get(base, base.upper())}
            for base in KNOWLEDGE_PATHS
        ]
        return {
            "disciplines": disciplines,
            "content_types": content_types,
            "bases": bases,
            "extensions": sorted(INGESTABLE_SUFFIXES),
        }

    def get_catalog(self, limit: int = 100) -> dict[str, Any]:
        rows = read_catalog()
        unique_rows = _dedupe_catalog_rows(rows)
        sliced = unique_rows[:limit]
        items = [
            {
                "id": row.get("id", ""),
                "filename": row.get("filename", Path(row.get("path", "")).name),
                "path": row.get("path", ""),
                "discipline": row.get("discipline") or [],
                "content_type": row.get("content_type", ""),
                "content_hash": row.get("content_hash"),
                "catalog_ts": row.get("catalog_ts"),
            }
            for row in sliced
        ]
        return {
            "total": len(unique_rows),
            "log_entries": len(rows),
            "items": items,
        }

    def get_stats(self) -> dict[str, Any]:
        router = get_knowledge_router()
        router._store.reload_from_disk()
        catalog = read_catalog()
        unique = _dedupe_catalog_rows(catalog)
        by_type = Counter(row.get("content_type", "unknown") for row in unique)
        return {
            "catalog_total": len(unique),
            "catalog_log_entries": len(catalog),
            "by_content_type": dict(by_type),
            "index": get_knowledge_router().stats(),
        }

    async def ingest_files(
        self,
        files: list[UploadFile],
        *,
        discipline: Optional[str] = None,
        content_type: Optional[str] = None,
        layer: str = "raw",
        force: bool = False,
        dry_run: bool = False,
        auto_index: bool = False,
        index_base: Optional[str] = None,
    ) -> dict[str, Any]:
        if not files:
            raise ValueError("Nenhum arquivo enviado")

        if content_type:
            content_type = normalize_content_type(content_type)

        tmp_dir = Path(tempfile.mkdtemp(prefix="knowledge_upload_"))
        saved: list[tuple[Path, str]] = []
        pre_errors: list[dict[str, str]] = []

        try:
            for upload in files:
                filename = upload.filename or "upload"
                suffix = Path(filename).suffix.lower()
                if suffix not in INGESTABLE_SUFFIXES:
                    pre_errors.append({
                        "filename": filename,
                        "error": f"Tipo não suportado ({suffix}). Use: {', '.join(sorted(INGESTABLE_SUFFIXES))}",
                    })
                    continue
                dest = tmp_dir / filename
                if dest.exists():
                    stem, ext = dest.stem, dest.suffix
                    counter = 2
                    while dest.exists():
                        dest = tmp_dir / f"{stem}_{counter}{ext}"
                        counter += 1
                content = await upload.read()
                dest.write_bytes(content)
                saved.append((dest, filename))

            if not saved and pre_errors:
                return {
                    "ingested": 0,
                    "skipped": 0,
                    "errors": pre_errors,
                    "results": [],
                    "indexing": None,
                }

            batch = get_ingester().ingest_batch(
                [path for path, _ in saved],
                discipline_hint=discipline,
                content_type_hint=content_type,
                layer=layer,
                force=force,
                copy=not dry_run,
            )

            results = []
            for record in batch.get("results", []):
                source_path = Path(record.get("source", ""))
                classification = record.get("classification") or {}
                results.append({
                    "filename": source_path.name,
                    "status": record.get("status", "unknown"),
                    "document_id": record.get("document_id"),
                    "target": record.get("target"),
                    "classification": {
                        "discipline_slug": classification.get("discipline_slug", ""),
                        "content_type": classification.get("content_type", ""),
                        "confidence": classification.get("confidence", 0),
                        "source": classification.get("source", ""),
                        "mapped_discipline": classification.get("mapped_discipline", ""),
                    }
                    if classification
                    else None,
                    "reason": record.get("reason"),
                })

            errors = [
                {"filename": Path(err.get("source", "")).name, "error": err.get("error", "")}
                for err in batch.get("errors", [])
            ] + pre_errors

            response: dict[str, Any] = {
                "ingested": batch.get("ingested", 0),
                "skipped": batch.get("skipped", 0),
                "errors": errors,
                "results": results,
                "indexing": None,
            }

            if auto_index and not dry_run and batch.get("ingested", 0) > 0:
                response["indexing"] = self._run_indexing(
                    force=force,
                    index_base=index_base,
                    content_types={
                        (r.get("classification") or {}).get("content_type")
                        for r in results
                        if r.get("status") == "copied"
                    },
                )

            return response
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def run_index(
        self,
        *,
        base: Optional[str] = None,
        force: bool = False,
        content_types: Optional[set[str | None]] = None,
    ) -> dict[str, Any]:
        return self._run_indexing(
            force=force,
            index_base=base,
            content_types=content_types,
        )

    def _run_indexing(
        self,
        *,
        force: bool = False,
        index_base: Optional[str] = None,
        content_types: Optional[set[str | None]] = None,
    ) -> dict[str, Any]:
        try:
            import pypdf  # noqa: F401
        except ImportError as exc:
            raise ValueError(
                "pypdf não instalado — necessário para indexar PDFs. "
                "Execute: pip install pypdf"
            ) from exc

        indexer = KnowledgeIndexer()

        if index_base:
            if index_base not in KNOWLEDGE_PATHS:
                raise ValueError(f"Base inválida: {index_base}. Use: {', '.join(KNOWLEDGE_PATHS)}")
            summary = indexer.index_base(index_base, force=force)
            get_multi_index_store().reload_from_disk()
            return {
                "mode": "single",
                "base": index_base,
                **summary,
            }

        if content_types:
            bases = {
                CONTENT_TYPE_TO_BASE_KEY[ct]
                for ct in content_types
                if ct and ct in CONTENT_TYPE_TO_BASE_KEY
            }
            if bases:
                combined: dict[str, Any] = {
                    "mode": "selected",
                    "bases": {},
                    "total_chunks": 0,
                    "errors": [],
                }
                for base_key in sorted(bases):
                    try:
                        base_summary = indexer.index_base(base_key, force=force)
                        combined["bases"][base_key] = base_summary
                        combined["total_chunks"] += base_summary.get("indexed_chunks", 0)
                    except Exception as exc:
                        combined["errors"].append({"base": base_key, "error": str(exc)})
                combined["total_chunks_in_store"] = indexer.multi_store.total_chunks()
                get_multi_index_store().reload_from_disk()
                return combined

        summary = indexer.index_all(force=force)
        summary["mode"] = "all"
        get_multi_index_store().reload_from_disk()
        return summary
