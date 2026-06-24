"""Gap analysis e indexação em lote — apenas PDFs licenciados / legislação pública."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from core.knowledge.catalog import read_catalog
from core.knowledge.multi_index_store import get_multi_index_store
from core.knowledge.norm_packs.legal import (
    COMMERCIAL_LEGAL_NOTICE,
    UPLOAD_INSTRUCTION,
    NormLegalSource,
    resolve_legal_source,
)
from core.knowledge.norm_packs.presets import NormPack, get_norm_pack, list_norm_packs
from core.knowledge.resolver import get_documents_dir
from memory.nbr_catalog import infer_discipline, parse_nbr_code
from memory.nbr_edition import chunk_edition_year, parse_edition_year
from memory.pdf_indexer import PDFIndexer

logger = logging.getLogger(__name__)


def _row_edition_year(row: dict, nbr_code: str) -> int:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    raw = row.get("edition_year") or meta.get("edition_year")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    filename = row.get("filename") or Path(row.get("path", "")).name
    return parse_edition_year(filename, nbr_code) or 0


def _path_edition_year(path: Path, nbr_code: str) -> int:
    return parse_edition_year(path.name, nbr_code) or 0


def _latest_edition_year(chunks: list[Any], nbr_code: str) -> int | None:
    years = [
        y
        for y in (chunk_edition_year(c) for c in chunks)
        if y is not None
    ]
    return max(years) if years else None


def _chunk_nbr_codes(base_key: str = "nbr") -> dict[str, int]:
    """Conta chunks indexados por código normativo."""
    from memory.nbr_catalog import resolve_norm_code

    store = get_multi_index_store().get_store(base_key)
    counts: dict[str, int] = {}
    for chunk in store.chunks:
        meta = chunk.metadata or {}
        code = resolve_norm_code(
            str(meta.get("filename") or chunk.source or ""),
            meta,
        )
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts


def _nbr_code_from_chunk(chunk) -> str | None:
    from memory.nbr_catalog import resolve_norm_code

    meta = chunk.metadata or {}
    return resolve_norm_code(
        str(meta.get("filename") or meta.get("path") or chunk.source or ""),
        meta,
    )


def _chunks_for_nbr(
    nbr_code: str,
    *,
    base_key: str = "nbr",
    max_chunks: int = 12,
    max_chars: int = 1200,
) -> list[dict[str, Any]]:
    """Trechos indexados no FAISS para uma NBR — somente edição mais recente."""
    store = get_multi_index_store().get_store(base_key)
    matched: list[tuple[int, Any]] = []
    for idx, chunk in enumerate(store.chunks):
        if _nbr_code_from_chunk(chunk) == nbr_code:
            matched.append((idx, chunk))

    if not matched:
        return []

    latest_year = _latest_edition_year([c for _, c in matched], nbr_code)
    if latest_year is not None:
        matched = [
            (idx, chunk)
            for idx, chunk in matched
            if chunk_edition_year(chunk) == latest_year
        ]

    matched.sort(key=lambda pair: (pair[1].page or 0, pair[0]))

    previews: list[dict[str, Any]] = []
    for chunk_index, chunk in matched[:max_chunks]:
        meta = chunk.metadata or {}
        text = (chunk.text or "").strip()
        edition_year = chunk_edition_year(chunk)
        previews.append(
            {
                "chunk_index": chunk_index,
                "page": chunk.page,
                "filename": meta.get("filename") or chunk.source,
                "edition_year": edition_year,
                "text": text[:max_chars] + ("…" if len(text) > max_chars else ""),
                "char_count": len(text),
            }
        )
    return previews


def _catalog_by_nbr(catalog_rows: list[dict]) -> dict[str, dict]:
    by_code: dict[str, dict] = {}
    for row in catalog_rows:
        filename = row.get("filename") or Path(row.get("path", "")).name
        code = parse_nbr_code(filename)
        if not code:
            continue
        existing = by_code.get(code)
        if not existing:
            by_code[code] = row
            continue
        row_year = _row_edition_year(row, code)
        existing_year = _row_edition_year(existing, code)
        if row_year > existing_year:
            by_code[code] = row
        elif row_year == existing_year and (row.get("catalog_ts") or "") >= (
            existing.get("catalog_ts") or ""
        ):
            by_code[code] = row
    return by_code


def _disk_by_nbr(documents_dir: Path) -> dict[str, Path]:
    by_code: dict[str, Path] = {}
    best_year: dict[str, int] = {}
    if not documents_dir.is_dir():
        return by_code
    for pdf in documents_dir.glob("*.pdf"):
        code = parse_nbr_code(pdf.name)
        if not code:
            continue
        year = _path_edition_year(pdf, code)
        if code not in by_code or year >= best_year.get(code, 0):
            by_code[code] = pdf
            best_year[code] = year
    return by_code


def _resolve_legal_source(row: Optional[dict], path: Optional[Path]) -> NormLegalSource:
    if path and path.is_file():
        return resolve_legal_source(row, file_path=path)
    if row:
        return resolve_legal_source(row)
    return NormLegalSource.MISSING


def _item_status(
    nbr_code: str,
    chunk_counts: dict[str, int],
    catalog: dict[str, dict],
    disk: dict[str, Path],
) -> dict[str, Any]:
    chunks = chunk_counts.get(nbr_code, 0)
    catalog_row = catalog.get(nbr_code)
    disk_path = disk.get(nbr_code)

    file_path: Optional[str] = None
    document_id: Optional[str] = None
    filename: Optional[str] = None

    if catalog_row:
        file_path = catalog_row.get("path")
        document_id = catalog_row.get("id")
        filename = catalog_row.get("filename") or Path(file_path or "").name
    elif disk_path:
        file_path = str(disk_path.resolve())
        filename = disk_path.name

    path_obj = Path(file_path) if file_path else None
    legal_source = (
        _resolve_legal_source(catalog_row, path_obj)
        if path_obj and path_obj.is_file()
        else NormLegalSource.MISSING
    )

    if chunks > 0:
        status = "indexed"
    elif path_obj and path_obj.is_file():
        status = "not_indexed"
    else:
        status = "missing"

    return {
        "nbr_code": nbr_code,
        "status": status,
        "chunk_count": chunks,
        "document_id": document_id,
        "filename": filename,
        "file_path": file_path,
        "legal_source": legal_source.value,
        "upload_instruction": UPLOAD_INSTRUCTION if status == "missing" else None,
    }


class NormPackService:
    """Catálogo + gap analysis + indexação em lote (sem geração de texto normativo)."""

    def list_packs(self) -> dict[str, Any]:
        return {
            "legal_notice": COMMERCIAL_LEGAL_NOTICE,
            "packs": list_norm_packs(),
        }

    def analyze_pack(self, pack_id: str) -> dict[str, Any]:
        pack = get_norm_pack(pack_id)
        catalog_rows = read_catalog()
        catalog = _catalog_by_nbr(catalog_rows)
        disk = _disk_by_nbr(get_documents_dir())
        chunk_counts = _chunk_nbr_codes()

        items: list[dict[str, Any]] = []
        for spec in pack.items:
            row = _item_status(spec.nbr_code, chunk_counts, catalog, disk)
            row.update(
                {
                    "title": spec.title,
                    "discipline": spec.discipline or infer_discipline(spec.nbr_code),
                    "critical": spec.critical,
                }
            )
            items.append(row)

        indexed = sum(1 for i in items if i["status"] == "indexed")
        not_indexed = sum(1 for i in items if i["status"] == "not_indexed")
        missing = sum(1 for i in items if i["status"] == "missing")
        critical_missing = sum(
            1 for i, spec in zip(items, pack.items) if spec.critical and i["status"] == "missing"
        )

        return {
            "pack_id": pack.id,
            "label": pack.label,
            "description": pack.description,
            "tags": list(pack.tags),
            "legal_notice": COMMERCIAL_LEGAL_NOTICE,
            "summary": {
                "total": len(items),
                "indexed": indexed,
                "not_indexed": not_indexed,
                "missing": missing,
                "critical_missing": critical_missing,
                "coverage_pct": round(100.0 * indexed / len(items), 1) if items else 0.0,
            },
            "items": items,
        }

    def index_pack(self, pack_id: str, *, force: bool = False) -> dict[str, Any]:
        """Indexa no FAISS NBR os PDFs licenciados presentes no pacote."""
        analysis = self.analyze_pack(pack_id)
        multi = get_multi_index_store()
        store = multi.get_store("nbr")
        pdf_indexer = PDFIndexer(store=store, embedder=multi.embedder)

        results: list[dict[str, Any]] = []
        indexed_chunks = 0
        errors: list[dict[str, str]] = []

        for item in analysis["items"]:
            code = item["nbr_code"]
            if item["status"] == "missing":
                results.append({"nbr_code": code, "status": "missing", "chunks": 0})
                continue
            if item["status"] == "indexed" and not force:
                results.append(
                    {
                        "nbr_code": code,
                        "status": "skipped",
                        "chunks": item["chunk_count"],
                    }
                )
                continue

            path = Path(item["file_path"] or "")
            if not path.is_file():
                results.append({"nbr_code": code, "status": "missing", "chunks": 0})
                continue

            if item["legal_source"] == NormLegalSource.MISSING.value:
                results.append({"nbr_code": code, "status": "missing", "chunks": 0})
                continue

            try:
                count = pdf_indexer.index_pdf(
                    pdf_path=path,
                    doc_type="nbr",
                    discipline=item["discipline"],
                    force=force,
                )
                indexed_chunks += count
                results.append({"nbr_code": code, "status": "indexed", "chunks": count})
            except Exception as exc:
                logger.exception("Falha ao indexar NBR %s", code)
                errors.append({"nbr_code": code, "error": str(exc)})
                results.append({"nbr_code": code, "status": "error", "chunks": 0, "error": str(exc)})

        store.save()

        return {
            "pack_id": pack_id,
            "force": force,
            "indexed_chunks": indexed_chunks,
            "results": results,
            "errors": errors,
            "analysis_summary": analysis["summary"],
        }

    def preview_pack(
        self,
        pack_id: str,
        *,
        nbr_code: str | None = None,
        max_chunks_per_nbr: int = 12,
    ) -> dict[str, Any]:
        """Preview dos trechos indexados (FAISS) para NBRs do pacote."""
        pack = get_norm_pack(pack_id)
        analysis = self.analyze_pack(pack_id)

        indexed_items = [i for i in analysis["items"] if i["status"] == "indexed"]
        if nbr_code:
            indexed_items = [i for i in indexed_items if i["nbr_code"] == nbr_code]
            if not indexed_items:
                pack_codes = {s.nbr_code for s in pack.items}
                if nbr_code not in pack_codes:
                    raise ValueError(f"NBR {nbr_code} não pertence ao pacote {pack_id}")
                raise ValueError(f"NBR {nbr_code} não está indexada no FAISS")

        previews: list[dict[str, Any]] = []
        for item in indexed_items:
            chunks = _chunks_for_nbr(
                item["nbr_code"],
                max_chunks=max_chunks_per_nbr,
            )
            edition_year = chunks[0]["edition_year"] if chunks else None
            previews.append(
                {
                    "nbr_code": item["nbr_code"],
                    "title": item["title"],
                    "filename": chunks[0]["filename"] if chunks else item.get("filename"),
                    "edition_year": edition_year,
                    "legal_source": item.get("legal_source"),
                    "chunk_count": item.get("chunk_count", 0),
                    "chunks": chunks,
                }
            )

        return {
            "pack_id": pack_id,
            "pack_label": pack.label,
            "nbr_code_filter": nbr_code,
            "indexed_count": len(previews),
            "items": previews,
            "preview_notice": (
                "Trechos extraídos do PDF licenciado indexado no FAISS — "
                "não substituem o documento oficial ABNT."
            ),
        }
