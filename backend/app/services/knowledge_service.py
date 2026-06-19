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
from core.concurrency import run_sync
from core.knowledge.ingestion import INGESTABLE_SUFFIXES, get_ingester, ingest_batch_sync
from core.knowledge.knowledge_base_router import get_knowledge_router
from core.knowledge.knowledge_indexer import KnowledgeIndexer
from core.knowledge.multi_index_store import get_multi_index_store
from core.knowledge.document_admin import delete_document, update_document_metadata

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
    "modelos_orcamento": "Modelo de orçamento (PPD/WBS)",
}

_BASE_LABELS: dict[str, str] = {
    "nbr": "NBR",
    "sinapi": "SINAPI",
    "tcpo": "TCPO",
    "tdr": "TDR",
    "catalogos": "Catálogos",
    "regional": "Regional",
    "budget_models": "Modelos de orçamento",
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
    @staticmethod
    def _active_price_document_id() -> str | None:
        from core.knowledge.price_registry import get_active_price_document_id

        return get_active_price_document_id()

    def activate_price_document(self, document_id: str) -> dict[str, Any]:
        from core.knowledge.price_registry import (
            get_active_price_document_id,
            load_active_price_rows,
            set_active_price_document,
        )

        catalog = _dedupe_catalog_rows(read_catalog())
        entry = next((row for row in catalog if row.get("id") == document_id), None)
        if not entry:
            raise ValueError("Documento não encontrado no catálogo")

        previous = get_active_price_document_id()
        set_active_price_document(document_id)
        loaded = load_active_price_rows()
        return {
            "activated": document_id,
            "name": loaded[0] if loaded else entry.get("name"),
            "item_count": len(loaded[1]) if loaded else entry.get("price_item_count", 0),
            "previous": previous,
        }

    def index_budget_model_document(self, document_id: str) -> dict[str, Any]:
        """Extrai WBS e indexa FAISS para documento já no catálogo (ex.: PPD como base de preço)."""
        from pathlib import Path

        from core.knowledge.ingestion import get_ingester
        from core.knowledge.metadata import read_metadata

        catalog = _dedupe_catalog_rows(read_catalog())
        entry = next((row for row in catalog if row.get("id") == document_id), None)
        if not entry:
            raise ValueError("Documento não encontrado no catálogo")

        path = Path(entry.get("path", ""))
        if not path.is_file():
            raise ValueError(f"Arquivo não encontrado: {path.name}")

        suffix = path.suffix.lower()
        if suffix not in (".xlsm", ".xlsx", ".xls", ".pdf", ".md", ".txt"):
            raise ValueError("Tipo de arquivo não suportado para modelo de orçamento")

        meta = read_metadata(path) or {}
        record: dict[str, Any] = {
            "content_hash": entry.get("content_hash", ""),
            "classification": {
                "discipline_slug": "orcamento",
                "content_type": "modelos_orcamento",
                "confidence": 1.0,
                "source": "manual",
                "mapped_discipline": "ORÇAMENTO",
            },
        }
        from core.knowledge.ingestion import ClassificationResult

        classification = ClassificationResult(
            discipline_slug="orcamento",
            content_type="modelos_orcamento",
            confidence=1.0,
            source="manual",
            mapped_discipline="ORÇAMENTO",
        )
        result = get_ingester()._attach_budget_model_to_existing(
            path,
            record,
            classification,
            name=entry.get("name") or meta.get("name"),
            description=entry.get("description") or meta.get("description"),
        )
        if result.get("status") == "error":
            raise ValueError(result.get("reason") or "Falha ao indexar modelo WBS")
        return {
            "document_id": document_id,
            "status": result.get("status"),
            "service_count": result.get("service_count", 0),
            "budget_model_indexed": result.get("budget_model_indexed", 0),
            "reason": result.get("reason"),
        }

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
        items = []
        for row in sliced:
            path = Path(row.get("path", ""))
            meta = {}
            if path.is_file():
                from core.knowledge.metadata import read_metadata

                meta = read_metadata(path) or {}
            items.append({
                "id": row.get("id", ""),
                "name": row.get("name") or row.get("filename", path.name),
                "description": row.get("description", ""),
                "filename": row.get("filename", path.name),
                "path": row.get("path", ""),
                "discipline": row.get("discipline") or [],
                "content_type": row.get("content_type", ""),
                "content_hash": row.get("content_hash"),
                "catalog_ts": row.get("catalog_ts"),
                "price_item_count": row.get("price_item_count", 0),
                "has_price_items": row.get("has_price_items", False),
                "has_budget_model": bool(
                    row.get("has_budget_model") or meta.get("has_budget_model")
                ),
                "service_count": row.get("service_count") or meta.get("service_count", 0),
                "is_active_price_base": row.get("id") == self._active_price_document_id(),
            })
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
        name: Optional[str] = None,
        description: Optional[str] = None,
        discipline: Optional[str] = None,
        content_type: Optional[str] = None,
        layer: str = "raw",
        force: bool = False,
        dry_run: bool = False,
        auto_index: bool = False,
        index_base: Optional[str] = None,
        register_price_base: bool = False,
        register_budget_model: bool = False,
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

            batch = await run_sync(
                ingest_batch_sync,
                [path for path, _ in saved],
                discipline_hint=discipline,
                content_type_hint=content_type,
                layer=layer,
                force=force,
                copy=not dry_run,
                name=name,
                description=description,
                register_price_base=register_price_base,
                register_budget_model=register_budget_model,
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
                    "price_item_count": record.get("price_item_count", 0),
                    "price_base_active": record.get("price_base_active", False),
                    "budget_model_indexed": record.get("budget_model_indexed", 0),
                    "service_count": record.get("service_count", 0),
                    "saved_as": record.get("saved_as"),
                    "storage_renamed": record.get("storage_renamed", False),
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

    def delete_document(self, document_id: str) -> dict[str, Any]:
        return delete_document(document_id)

    def update_document(
        self,
        document_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        content_type: Optional[str] = None,
        discipline: Optional[str] = None,
    ) -> dict[str, Any]:
        return update_document_metadata(
            document_id,
            name=name,
            description=description,
            content_type=content_type,
            discipline=discipline,
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
