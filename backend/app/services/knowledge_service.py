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
    CONTENT_TYPE_LABELS,
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
from core.knowledge.document_admin import (
    delete_document,
    purge_generic_legislation_imports,
    update_document_metadata,
)
from core.knowledge.document_type_presets import (
    DocumentTypePresetError,
    create_preset,
    delete_preset,
    list_presets,
    update_preset,
)

logger = logging.getLogger(__name__)

_CONTENT_TYPE_LABELS = CONTENT_TYPE_LABELS

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
            "document_type_presets": list_presets(),
        }

    def list_document_type_presets(self) -> dict[str, Any]:
        return {"presets": list_presets()}

    def create_document_type_preset(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            return create_preset(data)
        except DocumentTypePresetError as exc:
            raise ValueError(str(exc)) from exc

    def update_document_type_preset(self, preset_id: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            return update_preset(preset_id, data)
        except DocumentTypePresetError as exc:
            raise ValueError(str(exc)) from exc

    def delete_document_type_preset(self, preset_id: str) -> dict[str, Any]:
        try:
            return delete_preset(preset_id)
        except DocumentTypePresetError as exc:
            raise ValueError(str(exc)) from exc

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
                "name": (
                    meta.get("norm_display_name")
                    or meta.get("name")
                    or row.get("name")
                    or row.get("filename", path.name)
                ),
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
        try:
            router._store.reload_from_disk()
        except Exception as exc:
            logger.warning("Stats: reload FAISS ignorado (%s)", exc)
        catalog = read_catalog()
        unique = _dedupe_catalog_rows(catalog)
        by_type = Counter(row.get("content_type", "unknown") for row in unique)
        from core.knowledge.catalog_stats import compute_norm_catalog_stats
        from core.knowledge.index_coverage import compute_nbr_index_coverage

        return {
            "catalog_total": len(unique),
            "catalog_log_entries": len(catalog),
            "catalog_superseded": max(0, len(catalog) - len(unique)),
            "by_content_type": dict(by_type),
            "index": get_knowledge_router().stats(),
            "norms": compute_norm_catalog_stats(unique),
            "nbr_coverage": compute_nbr_index_coverage(unique),
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
                if not content:
                    pre_errors.append({
                        "filename": filename,
                        "error": "Arquivo vazio — verifique o PDF e tente novamente.",
                    })
                    continue
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
        from core.runtime.job_tracking import track_sync_job

        label = f"Indexação FAISS — {base or 'todas as bases'}"

        with track_sync_job(kind="knowledge", label=label) as job:

            def on_progress(data: dict[str, Any]) -> None:
                current = int(data.get("current") or 0)
                total = int(data.get("total") or 0)
                should_log = (
                    current <= 1
                    or (total > 0 and current >= total)
                    or current % 10 == 0
                )
                job.update(
                    phase="index",
                    message=data.get("message"),
                    current=current,
                    total=total,
                    percent=int(data.get("percent") or 0),
                    log=should_log,
                )

            return self._run_indexing(
                force=force,
                index_base=base,
                content_types=content_types,
                on_progress=on_progress if base else None,
            )

    def delete_document(self, document_id: str) -> dict[str, Any]:
        return delete_document(document_id)

    def purge_generic_legislation_imports(self, *, dry_run: bool = False) -> dict[str, Any]:
        return purge_generic_legislation_imports(dry_run=dry_run)

    def run_maintenance(
        self,
        *,
        purge_orphans: bool = True,
        dedupe_catalog: bool = True,
        repair_norms: bool = True,
        compact_faiss: bool = True,
        index_pending: bool = True,
        dry_run: bool = False,
        on_progress: Optional[Any] = None,
    ) -> dict[str, Any]:
        from config.settings import NBR_DIR
        from core.knowledge.catalog_maintenance import (
            dedupe_catalog_by_path,
            purge_orphan_catalog_entries,
            repair_priority_norm_sidecars,
        )
        from core.knowledge.faiss_maintenance import maintain_all_faiss
        from core.knowledge.pending_indexer import index_pending_nbr_pdfs

        result: dict[str, Any] = {}

        if purge_orphans:
            result["purge_orphans"] = purge_orphan_catalog_entries(dry_run=dry_run)
        if dedupe_catalog:
            result["dedupe_catalog"] = dedupe_catalog_by_path(dry_run=dry_run)
        if repair_norms:
            result["repair_norms"] = repair_priority_norm_sidecars(
                NBR_DIR, dry_run=dry_run
            )
        if compact_faiss and not dry_run:
            result["compact_faiss"] = maintain_all_faiss(compact=True, reembed=False)
        if index_pending and not dry_run:
            result["index_pending"] = index_pending_nbr_pdfs(on_progress=on_progress)

        rows = read_catalog()
        from core.knowledge.index_coverage import compute_nbr_index_coverage

        result["coverage"] = compute_nbr_index_coverage(rows)
        get_multi_index_store().reload_from_disk()
        return result

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
        on_progress: Optional[Any] = None,
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
            summary = indexer.index_base(index_base, force=force, on_progress=on_progress)
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
                        base_summary = indexer.index_base(base_key, force=force, on_progress=on_progress)
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

    async def ingest_from_web(
        self,
        *,
        page_url: str,
        discipline: str | None = None,
        content_type: str | None = None,
        description_prefix: str = "",
        max_files: int = 50,
        force: bool = False,
        auto_index: bool = True,
    ) -> dict[str, Any]:
        from core.knowledge.web_ingest import bulk_ingest_from_page
        from core.knowledge.web_ingest.security import UnsafeURLError

        ct = normalize_content_type(content_type) if content_type else None

        try:
            result = await run_sync(
                bulk_ingest_from_page,
                page_url,
                discipline=discipline,
                content_type=ct,
                description_prefix=description_prefix,
                max_files=max_files,
                force=force,
            )
        except UnsafeURLError as exc:
            raise ValueError(str(exc)) from exc

        if auto_index and result.get("ingested", 0) > 0:
            result["indexing"] = self._run_indexing(
                force=force,
                index_base="nbr" if ct == "nbrs" else None,
                content_types={ct} if ct else None,
            )

        return result

    def ingest_from_web_stream_events(
        self,
        *,
        page_url: str,
        discipline: str | None = None,
        content_type: str | None = None,
        description_prefix: str = "",
        max_files: int = 50,
        force: bool = False,
        auto_index: bool = True,
    ):
        """Gera eventos SSE (progress / done / error) durante importação web."""
        import queue
        import threading

        from core.knowledge.web_ingest import bulk_ingest_from_page
        from core.runtime.job_tracking import track_sync_job
        from core.stream_events import format_sse

        q: queue.Queue[tuple[str, Any]] = queue.Queue()
        ct = normalize_content_type(content_type) if content_type else None
        label = f"Importação web — {page_url[:72]}"

        def _scale_progress(data: dict[str, Any]) -> dict[str, Any]:
            phase = str(data.get("phase") or "")
            raw = int(data.get("percent") or 0)
            if phase == "parse":
                pct = 8 if raw >= 100 else 3
            elif phase in ("download", "ingest"):
                pct = 8 + round(raw * 0.82)
            else:
                pct = raw
            return {**data, "percent": min(100, max(0, pct))}

        def worker() -> None:
            try:
                with track_sync_job(kind="knowledge_import", label=label) as runtime_job:

                    def on_progress(data: dict[str, Any]) -> None:
                        scaled = _scale_progress(data)
                        runtime_job.update(
                            phase=str(scaled.get("phase") or "ingest"),
                            message=scaled.get("message"),
                            current=scaled.get("current"),
                            total=scaled.get("total"),
                            percent=scaled.get("percent"),
                            log=bool(scaled.get("message")),
                        )
                        q.put(("progress", scaled))

                    result = bulk_ingest_from_page(
                        page_url,
                        discipline=discipline,
                        content_type=ct,
                        description_prefix=description_prefix,
                        max_files=max_files,
                        force=force,
                        on_progress=on_progress,
                    )

                    if auto_index and result.get("ingested", 0) > 0:
                        def on_index_progress(data: dict[str, Any]) -> None:
                            inner_pct = int(data.get("percent") or 0)
                            scaled = {
                                **data,
                                "percent": min(100, 92 + round(inner_pct * 0.08)),
                                "phase": "index",
                            }
                            runtime_job.update(
                                phase="index",
                                message=data.get("message"),
                                current=data.get("current"),
                                total=data.get("total"),
                                percent=scaled["percent"],
                                log=(
                                    int(data.get("current") or 0) <= 1
                                    or int(data.get("current") or 0) % 25 == 0
                                ),
                            )
                            q.put(("progress", scaled))

                        q.put(
                            (
                                "progress",
                                {
                                    "phase": "index",
                                    "current": 0,
                                    "total": 1,
                                    "percent": 92,
                                    "message": "Indexando FAISS para busca pela IA…",
                                    "name": None,
                                },
                            )
                        )
                        runtime_job.update(
                            phase="index",
                            message="Indexando FAISS para busca pela IA…",
                            percent=92,
                        )
                        result["indexing"] = self._run_indexing(
                            force=force,
                            index_base="nbr" if ct == "nbrs" else None,
                            content_types={ct} if ct else None,
                            on_progress=on_index_progress,
                        )
                        runtime_job.update(
                            phase="index",
                            message="Indexação concluída",
                            percent=100,
                        )
                        q.put(
                            (
                                "progress",
                                {
                                    "phase": "index",
                                    "current": 1,
                                    "total": 1,
                                    "percent": 100,
                                    "message": "Indexação concluída",
                                    "name": None,
                                },
                            )
                        )

                    q.put(("done", result))
            except Exception as exc:
                logger.exception("Falha na ingestão web (stream)")
                q.put(("error", {"error": str(exc)}))

        threading.Thread(target=worker, daemon=True).start()

        while True:
            kind, payload = q.get()
            if kind == "progress":
                yield format_sse("progress", payload)
            elif kind == "done":
                yield format_sse("done", payload)
                break
            elif kind == "error":
                yield format_sse("error", payload)
                break

    async def save_norm_uploads(
        self,
        files: list[Any],
        *,
        max_files: int | None = None,
    ) -> tuple[Any, list[Path], list[dict[str, str]]]:
        """Salva uploads PDF em diretório temporário para ingestão em lote de normas."""
        from core.knowledge.norm_bulk.constants import NORM_BULK_MAX_FILES
        from core.knowledge.norm_bulk.upload_utils import is_upload_file

        limit = max_files if max_files is not None else NORM_BULK_MAX_FILES

        tmp_dir = Path(tempfile.mkdtemp(prefix="norm_bulk_"))
        saved: list[Path] = []
        errors: list[dict[str, str]] = []

        for upload in files:
            if not is_upload_file(upload):
                continue
            filename = Path(upload.filename or "documento.pdf").name
            if not filename.lower().endswith(".pdf"):
                errors.append({"filename": filename, "error": "Apenas PDFs são aceitos neste lote"})
                continue
            dest = tmp_dir / filename
            if dest.exists():
                stem, ext = dest.stem, dest.suffix
                counter = 2
                while dest.exists():
                    dest = tmp_dir / f"{stem}_{counter}{ext}"
                    counter += 1
            content = await upload.read()
            if not content:
                errors.append({"filename": filename, "error": "Arquivo vazio"})
                continue
            dest.write_bytes(content)
            saved.append(dest)

        if len(saved) > limit:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ValueError(f"Máximo {limit} PDFs por lote (recebidos: {len(saved)})")

        return tmp_dir, saved, errors

    def ingest_norms_stream_events(
        self,
        sources: list[Path],
        *,
        force: bool = False,
        use_ai_fallback: bool = False,
        mark_edition_outdated: bool = False,
        auto_index: bool = True,
        pre_errors: list[dict[str, str]] | None = None,
        cleanup_dir: Path | None = None,
    ):
        """SSE para importação em lote de NBRs/NRs."""
        import queue
        import threading

        from core.knowledge.norm_bulk.service import bulk_ingest_norm_pdfs
        from core.runtime.job_tracking import track_sync_job
        from core.stream_events import format_sse

        q: queue.Queue[tuple[str, Any]] = queue.Queue()
        label = f"Importação NBR/NR ({len(sources)} PDFs)"

        def worker() -> None:
            try:
                with track_sync_job(kind="norm_bulk", label=label) as runtime_job:

                    def on_ingest_progress(data: dict[str, Any]) -> None:
                        runtime_job.update(
                            phase=str(data.get("phase") or "ingest"),
                            message=data.get("message"),
                            current=data.get("current"),
                            total=data.get("total"),
                            percent=data.get("percent"),
                            log=bool(data.get("message")),
                        )
                        q.put(("progress", data))

                    result = bulk_ingest_norm_pdfs(
                        sources,
                        force=force,
                        use_ai_fallback=use_ai_fallback,
                        mark_edition_outdated=mark_edition_outdated,
                        on_progress=on_ingest_progress,
                    )
                    if pre_errors:
                        result.setdefault("errors", [])
                        result["errors"] = list(result.get("errors", [])) + pre_errors

                    if auto_index and result.get("ingested", 0) > 0:
                        def on_index_progress(data: dict[str, Any]) -> None:
                            inner_pct = int(data.get("percent") or 0)
                            scaled = {
                                **data,
                                "percent": min(100, 92 + round(inner_pct * 0.08)),
                            }
                            current = int(data.get("current") or 0)
                            total = int(data.get("total") or 0)
                            should_log = (
                                current <= 1
                                or (total > 0 and current >= total)
                                or current % 25 == 0
                            )
                            runtime_job.update(
                                phase="index",
                                message=data.get("message"),
                                current=current,
                                total=total,
                                percent=scaled["percent"],
                                log=should_log,
                            )
                            q.put(("progress", scaled))

                        runtime_job.update(
                            phase="index",
                            message="Indexando base NBR (FAISS)…",
                            percent=92,
                        )
                        q.put(
                            (
                                "progress",
                                {
                                    "phase": "index",
                                    "current": 0,
                                    "total": 1,
                                    "percent": 92,
                                    "message": "Indexando base NBR (FAISS)…",
                                    "name": None,
                                },
                            )
                        )
                        result["indexing"] = self._run_indexing(
                            force=force,
                            index_base="nbr",
                            content_types={"nbrs"},
                            on_progress=on_index_progress,
                        )
                        runtime_job.update(
                            phase="index",
                            message="Indexação NBR concluída",
                            percent=100,
                        )
                        q.put(
                            (
                                "progress",
                                {
                                    "phase": "index",
                                    "current": 1,
                                    "total": 1,
                                    "percent": 100,
                                    "message": "Indexação NBR concluída",
                                    "name": None,
                                },
                            )
                        )

                    q.put(("done", result))
            except Exception as exc:
                logger.exception("Falha na ingestão em lote de normas (stream)")
                q.put(("error", {"error": str(exc)}))
            finally:
                if cleanup_dir:
                    shutil.rmtree(cleanup_dir, ignore_errors=True)

        threading.Thread(target=worker, daemon=True).start()

        while True:
            kind, payload = q.get()
            if kind == "progress":
                yield format_sse("progress", payload)
            elif kind == "done":
                yield format_sse("done", payload)
                break
            elif kind == "error":
                yield format_sse("error", payload)
                break

    def list_norm_packs(self) -> dict[str, Any]:
        from core.knowledge.norm_packs.service import NormPackService

        return NormPackService().list_packs()

    def analyze_norm_pack(self, pack_id: str) -> dict[str, Any]:
        from core.knowledge.norm_packs.service import NormPackService

        return NormPackService().analyze_pack(pack_id)

    def index_norm_pack(self, pack_id: str, *, force: bool = False) -> dict[str, Any]:
        from core.knowledge.norm_packs.service import NormPackService

        return NormPackService().index_pack(pack_id, force=force)

    def preview_norm_pack(
        self,
        pack_id: str,
        *,
        nbr_code: str | None = None,
    ) -> dict[str, Any]:
        from core.knowledge.norm_packs.service import NormPackService

        return NormPackService().preview_pack(pack_id, nbr_code=nbr_code)

    def export_norm_pack_gap_csv(self, pack_id: str) -> tuple[str, str]:
        from core.knowledge.norm_packs.gap_export import export_pack_gap_csv

        return export_pack_gap_csv(pack_id)

    def export_project_norm_gaps_csv(self, gaps: dict[str, Any]) -> tuple[str, str]:
        from core.knowledge.norm_packs.gap_export import export_project_gaps_csv

        return export_project_gaps_csv(gaps)
