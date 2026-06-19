"""
Knowledge Indexer — indexa PDFs/CSV/Excel em índices FAISS separados por base.

Somente invocado por scripts manuais — nunca por Evolution/Agent Generation loops.

REGRA: backend/knowledge/ = write+read
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Optional

from config import settings
from core.knowledge.constants import IMMUTABLE_KNOWLEDGE_BASES, KNOWLEDGE_PATHS, BASE_DOC_TYPES
from core.knowledge.multi_index_store import MultiIndexKnowledgeStore, get_multi_index_store
from core.knowledge.metadata import file_matches_base, read_metadata
from core.knowledge.resolver import (
    ensure_canonical_dir,
    file_dedup_key,
    file_hash_dedup_key,
    get_all_read_paths,
    is_legacy_path,
)
from memory.chunker import split_text
from memory.embeddings import NomicEmbedder
from memory.models import DocumentChunk
from memory.nbr_catalog import infer_discipline, parse_nbr_code
from memory.pdf_indexer import PDFIndexer

logger = logging.getLogger(__name__)


class KnowledgeIndexer:
    """Indexação versionada e imutável em runtime."""

    def __init__(
        self,
        multi_store: Optional[MultiIndexKnowledgeStore] = None,
        embedder: Optional[NomicEmbedder] = None,
    ) -> None:
        if not IMMUTABLE_KNOWLEDGE_BASES:
            logger.warning("IMMUTABLE_KNOWLEDGE_BASES=false — use apenas em dev")
        self.multi_store = multi_store or get_multi_index_store()
        self.embedder = embedder or NomicEmbedder()

    def index_all(self, force: bool = False) -> dict[str, Any]:
        summary: dict[str, Any] = {"bases": {}, "total_chunks": 0, "errors": []}
        for base_key in KNOWLEDGE_PATHS:
            try:
                base_summary = self.index_base(base_key, force=force)
                summary["bases"][base_key] = base_summary
                summary["total_chunks"] += base_summary.get("indexed_chunks", 0)
            except Exception as exc:
                summary["errors"].append({"base": base_key, "error": str(exc)})
        summary["total_chunks_in_store"] = self.multi_store.total_chunks()
        return summary

    def index_base(self, base_key: str, force: bool = False) -> dict[str, Any]:
        store = self.multi_store.get_store(base_key)
        doc_type = BASE_DOC_TYPES.get(base_key, base_key)
        summary = {
            "base": base_key,
            "indexed_files": 0,
            "skipped_files": 0,
            "deduped_files": 0,
            "indexed_chunks": 0,
            "errors": [],
            "files": [],
        }

        include_discipline = True
        discipline_first = True
        use_hash_dedup = True

        ensure_canonical_dir(base_key)
        seen_dedup: set[str] = set()

        for directory, tier in get_all_read_paths(
            base_key,
            include_legacy=True,
            include_discipline=include_discipline,
            discipline_first=discipline_first,
        ):
            if not directory.exists():
                if tier == "legacy_readonly":
                    logger.debug("Legacy path ausente (ok): %s", directory)
                continue
            summary["files"].extend(
                self._index_directory(
                    store,
                    directory,
                    base_key,
                    doc_type,
                    force,
                    summary,
                    seen_dedup,
                    tier,
                    use_hash_dedup,
                )
            )

        store.save()
        return summary

    def _dedup_key(self, path: Path, use_hash: bool, base_key: str = "") -> str:
        if base_key == "nbr":
            nbr = parse_nbr_code(path.name)
            if nbr:
                from memory.nbr_edition import parse_edition_year

                year = parse_edition_year(path.name, nbr)
                if year:
                    return f"nbr:{nbr}:{year}"
                return f"nbr:{nbr}:{file_dedup_key(path)}"
        if use_hash and path.is_file() and path.stat().st_size <= 50 * 1024 * 1024:
            try:
                return file_hash_dedup_key(path)
            except OSError:
                pass
        return file_dedup_key(path)

    def _index_directory(
        self,
        store,
        directory: Path,
        base_key: str,
        doc_type: str,
        force: bool,
        summary: dict,
        seen_dedup: set[str],
        tier: str,
        use_hash_dedup: bool = False,
    ) -> list[dict]:
        file_results: list[dict] = []
        pdf_indexer = PDFIndexer(store=store, embedder=self.embedder)

        for pdf_path in sorted(directory.glob("*.pdf")):
            if not file_matches_base(pdf_path, base_key):
                continue
            dedup = self._dedup_key(pdf_path, use_hash_dedup, base_key=base_key)
            if dedup in seen_dedup:
                summary["deduped_files"] += 1
                file_results.append(
                    {"file": pdf_path.name, "status": "deduped", "tier": tier, "chunks": 0}
                )
                logger.info(
                    "Dedup: %s ignorado (já indexado de fonte canônica)", pdf_path.name
                )
                continue
            seen_dedup.add(dedup)

            try:
                discipline = ""
                if base_key == "nbr":
                    nbr = parse_nbr_code(pdf_path.name)
                    discipline = infer_discipline(nbr) if nbr else ""
                count = pdf_indexer.index_pdf(
                    pdf_path=pdf_path,
                    doc_type=doc_type,
                    discipline=discipline,
                    force=force,
                )
                meta = read_metadata(pdf_path) or {}
                self._record_file(
                    summary, file_results, pdf_path.name, count, tier,
                    content_type=meta.get("content_type"),
                )
            except Exception as exc:
                summary["errors"].append({"file": str(pdf_path), "error": str(exc)})

        for csv_path in sorted(directory.glob("*.csv")):
            if not file_matches_base(csv_path, base_key):
                continue
            dedup = self._dedup_key(csv_path, use_hash_dedup, base_key=base_key)
            if dedup in seen_dedup:
                summary["deduped_files"] += 1
                file_results.append(
                    {"file": csv_path.name, "status": "deduped", "tier": tier, "chunks": 0}
                )
                continue
            seen_dedup.add(dedup)

            try:
                count = self._index_csv(store, csv_path, base_key, doc_type, force, tier)
                self._record_file(summary, file_results, csv_path.name, count, tier)
            except Exception as exc:
                summary["errors"].append({"file": str(csv_path), "error": str(exc)})

        for pattern in ("*.xlsx", "*.xls"):
            for xlsx_path in sorted(directory.glob(pattern)):
                if not file_matches_base(xlsx_path, base_key):
                    continue
                dedup = self._dedup_key(xlsx_path, use_hash_dedup, base_key=base_key)
                if dedup in seen_dedup:
                    summary["deduped_files"] += 1
                    file_results.append(
                        {"file": xlsx_path.name, "status": "deduped", "tier": tier, "chunks": 0}
                    )
                    continue
                seen_dedup.add(dedup)

                try:
                    count = self._index_excel(
                        store, xlsx_path, base_key, doc_type, force, tier
                    )
                    self._record_file(summary, file_results, xlsx_path.name, count, tier)
                except Exception as exc:
                    summary["errors"].append({"file": str(xlsx_path), "error": str(exc)})

        if is_legacy_path(directory):
            logger.debug("Indexado path legado read-only: %s", directory)

        return file_results

    def _index_csv(
        self,
        store,
        csv_path: Path,
        base_key: str,
        doc_type: str,
        force: bool,
        tier: str,
    ) -> int:
        file_key = str(csv_path.resolve())
        if store.is_indexed(file_key) and not force:
            return 0
        if force and store.is_indexed(file_key):
            store.remove_by_path(file_key)

        chunks: list[DocumentChunk] = []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
                if not text.strip():
                    continue
                for piece in split_text(text):
                    embedding = self.embedder.embed_document(piece)
                    chunks.append(
                        DocumentChunk(
                            text=piece,
                            embedding=embedding,
                            source=csv_path.stem,
                            doc_type=doc_type,
                            discipline=base_key.upper(),
                            metadata={
                                "path": file_key,
                                "filename": csv_path.name,
                                "knowledge_base": base_key,
                                "source_tier": tier,
                                "content_type": (read_metadata(csv_path) or {}).get(
                                    "content_type"
                                ),
                                "row": row_num,
                                "format": "csv",
                            },
                        )
                    )
        return store.add_many(chunks) if chunks else 0

    def _index_excel(
        self,
        store,
        xlsx_path: Path,
        base_key: str,
        doc_type: str,
        force: bool,
        tier: str,
    ) -> int:
        try:
            import openpyxl
        except ImportError as exc:
            raise ImportError(
                "openpyxl necessário para indexar Excel: pip install openpyxl"
            ) from exc

        file_key = str(xlsx_path.resolve())
        if store.is_indexed(file_key) and not force:
            return 0
        if force and store.is_indexed(file_key):
            store.remove_by_path(file_key)

        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return 0

        headers = [str(h or f"col{i}") for i, h in enumerate(rows[0])]
        chunks: list[DocumentChunk] = []
        for row_num, row in enumerate(rows[1:], start=2):
            cells = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
            text = " | ".join(f"{k}: {v}" for k, v in cells.items() if v is not None)
            if not text.strip():
                continue
            for piece in split_text(text):
                embedding = self.embedder.embed_document(piece)
                chunks.append(
                    DocumentChunk(
                        text=piece,
                        embedding=embedding,
                        source=xlsx_path.stem,
                        doc_type=doc_type,
                        discipline=base_key.upper(),
                        metadata={
                            "path": file_key,
                            "filename": xlsx_path.name,
                            "knowledge_base": base_key,
                            "source_tier": tier,
                            "row": row_num,
                            "format": "xlsx",
                        },
                    )
                )
        wb.close()
        return store.add_many(chunks) if chunks else 0

    @staticmethod
    def _record_file(
        summary: dict,
        files: list,
        name: str,
        count: int,
        tier: str = "canonical",
        content_type: str | None = None,
    ) -> None:
        extra = {"content_type": content_type} if content_type else {}
        if count == 0:
            summary["skipped_files"] += 1
            files.append(
                {"file": name, "status": "skipped", "tier": tier, "chunks": 0, **extra}
            )
        else:
            summary["indexed_files"] += 1
            summary["indexed_chunks"] += count
            files.append(
                {"file": name, "status": "indexed", "tier": tier, "chunks": count, **extra}
            )
