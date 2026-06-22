"""
Indexação de PDFs pendentes (ITs, normas prioritárias, OCR).

Usado pelo script knowledge_maintenance e API /knowledge/maintenance.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

from config.settings import NBR_DIR
from core.knowledge.catalog import read_catalog
from core.knowledge.index_coverage import compute_nbr_index_coverage
from core.knowledge.knowledge_indexer import KnowledgeIndexer
from core.knowledge.metadata import file_matches_base
from core.knowledge.multi_index_store import get_multi_index_store
from core.knowledge.pdf_text_extractor import extract_pdf_pages
from memory.pdf_indexer import PDFIndexer

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]


def _indexed_paths(base_key: str = "nbr") -> set[str]:
    store = get_multi_index_store().get_store(base_key)
    paths: set[str] = set()
    for chunk in store.chunks:
        raw = (chunk.metadata or {}).get("path")
        if raw:
            try:
                paths.add(str(Path(raw).resolve()))
            except OSError:
                paths.add(str(raw))
    return paths


def list_pending_nbr_pdfs(
    documents_dir: Path | None = None,
    *,
    include_2019_its: bool = True,
    priority_codes: tuple[str, ...] = ("9077", "14833"),
) -> list[Path]:
    """PDFs NBR no disco ainda não presentes no FAISS."""
    documents_dir = Path(documents_dir or NBR_DIR)
    indexed = _indexed_paths("nbr")
    pending: list[Path] = []

    for pdf_path in sorted(documents_dir.glob("*.pdf")):
        if not file_matches_base(pdf_path, "nbr"):
            continue
        try:
            resolved = str(pdf_path.resolve())
        except OSError:
            resolved = str(pdf_path)
        if resolved in indexed:
            continue

        name = pdf_path.name
        is_2019_it = name.startswith("2019_-")
        is_priority = any(code in name for code in priority_codes)
        if is_2019_it and not include_2019_its and not is_priority:
            continue
        pending.append(pdf_path)

    return pending


def index_pending_nbr_pdfs(
    *,
    force: bool = True,
    include_2019_its: bool = True,
    priority_codes: tuple[str, ...] = ("9077", "14833"),
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Indexa PDFs pendentes com extrator enriquecido (PyMuPDF + OCR)."""
    pending = list_pending_nbr_pdfs(
        include_2019_its=include_2019_its,
        priority_codes=priority_codes,
    )
    total = len(pending)
    summary: dict[str, Any] = {
        "pending_files": total,
        "indexed_files": 0,
        "indexed_chunks": 0,
        "ocr_files": 0,
        "empty_files": 0,
        "errors": [],
        "files": [],
    }

    if total == 0:
        return summary

    indexer = KnowledgeIndexer()
    store = indexer.multi_store.get_store("nbr")
    pdf_indexer = PDFIndexer(store=store, embedder=indexer.embedder)
    indexer.embedder.warmup()

    for current, pdf_path in enumerate(pending, start=1):
        if on_progress:
            on_progress(
                {
                    "phase": "index",
                    "current": current,
                    "total": total,
                    "percent": round(current / total * 100),
                    "message": f"Indexando {pdf_path.name} ({current}/{total})",
                    "name": pdf_path.name,
                }
            )
        try:
            from core.knowledge import pdf_text_extractor as pte

            pages = extract_pdf_pages(pdf_path)
            if not pte._extract_pypdf(pdf_path) and pages:
                summary["ocr_files"] += 1

            if not pages:
                summary["empty_files"] += 1
                summary["files"].append(
                    {"file": pdf_path.name, "status": "empty", "chunks": 0}
                )
                continue

            count = pdf_indexer.index_pdf(
                pdf_path=pdf_path,
                doc_type="nbr",
                force=force,
                pages=pages,
            )
            if count > 0:
                summary["indexed_files"] += 1
                summary["indexed_chunks"] += count
                summary["files"].append(
                    {"file": pdf_path.name, "status": "indexed", "chunks": count}
                )
                store.save()
            else:
                summary["files"].append(
                    {"file": pdf_path.name, "status": "skipped", "chunks": 0}
                )
        except Exception as exc:
            summary["errors"].append({"file": str(pdf_path), "error": str(exc)})
            logger.warning("Falha ao indexar %s: %s", pdf_path.name, exc)

        time.sleep(0.25)

    store.save()
    get_multi_index_store().reload_from_disk()
    rows = read_catalog()
    summary["coverage"] = compute_nbr_index_coverage(rows)
    return summary
