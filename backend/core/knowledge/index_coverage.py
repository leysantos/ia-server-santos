"""Cobertura catálogo ↔ índice FAISS (base NBR)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.knowledge.metadata import read_metadata
from core.knowledge.multi_index_store import get_multi_index_store
from memory.nbr_catalog import parse_nbr_code, resolve_norm_code

_NORM_CONTENT_TYPES = frozenset({"nbrs", "nbr"})


def _norm_code_from_row(row: dict[str, Any]) -> str | None:
    path = Path(str(row.get("path") or ""))
    filename = str(row.get("filename") or path.name or "")
    meta = read_metadata(path) if path.is_file() else {}
    return resolve_norm_code(filename, meta)


def _indexed_paths_and_codes(base_key: str = "nbr") -> tuple[set[str], set[str]]:
    store = get_multi_index_store().get_store(base_key)
    paths: set[str] = set()
    codes: set[str] = set()
    for chunk in store.chunks:
        meta = chunk.metadata or {}
        raw_path = meta.get("path")
        if raw_path:
            try:
                paths.add(str(Path(raw_path).resolve()))
            except OSError:
                paths.add(str(raw_path))
        code = resolve_norm_code(
            str(meta.get("filename") or chunk.source or ""),
            meta,
        )
        if code:
            codes.add(code)
    return paths, codes


def compute_nbr_index_coverage(catalog_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compara PDFs NBR/NR no catálogo com arquivos presentes no FAISS."""
    indexed_paths, indexed_codes = _indexed_paths_and_codes("nbr")
    store = get_multi_index_store().get_store("nbr")
    faiss_chunks = store.count()

    catalog_paths: set[str] = set()
    catalog_codes: set[str] = set()
    catalog_files = 0
    files_on_disk = 0
    files_missing_disk = 0

    for row in catalog_rows:
        content_type = str(row.get("content_type") or "")
        if content_type not in _NORM_CONTENT_TYPES:
            continue
        catalog_files += 1
        path = Path(str(row.get("path") or ""))
        if not path.is_file():
            files_missing_disk += 1
            continue
        files_on_disk += 1
        try:
            catalog_paths.add(str(path.resolve()))
        except OSError:
            catalog_paths.add(str(path))
        code = _norm_code_from_row(row)
        if code:
            catalog_codes.add(code)

    files_covered = catalog_paths & indexed_paths
    files_covered_by_code: set[str] = set()
    for row in catalog_rows:
        content_type = str(row.get("content_type") or "")
        if content_type not in _NORM_CONTENT_TYPES:
            continue
        path = Path(str(row.get("path") or ""))
        if not path.is_file():
            continue
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved in files_covered:
            continue
        code = _norm_code_from_row(row)
        if code and code in indexed_codes:
            files_covered_by_code.add(resolved)
    effective_covered = files_covered | files_covered_by_code
    files_not_indexed = sorted(
        Path(p).name for p in (catalog_paths - effective_covered)
    )
    codes_covered = catalog_codes & indexed_codes
    codes_not_indexed = sorted(catalog_codes - indexed_codes)

    file_coverage_pct = (
        round(100.0 * len(files_covered) / len(catalog_paths), 1) if catalog_paths else 0.0
    )
    effective_file_coverage_pct = (
        round(100.0 * len(effective_covered) / len(catalog_paths), 1)
        if catalog_paths
        else 0.0
    )
    code_coverage_pct = (
        round(100.0 * len(codes_covered) / len(catalog_codes), 1) if catalog_codes else 0.0
    )
    display_coverage_pct = max(file_coverage_pct, effective_file_coverage_pct, code_coverage_pct)

    return {
        "base": "nbr",
        "catalog_files": catalog_files,
        "files_on_disk": files_on_disk,
        "files_missing_disk": files_missing_disk,
        "indexed_files": len(files_covered),
        "effective_indexed_files": len(effective_covered),
        "dedup_only_files": len(files_covered_by_code),
        "not_indexed_files": len(catalog_paths - effective_covered),
        "catalog_codes": len(catalog_codes),
        "indexed_codes": len(codes_covered),
        "not_indexed_codes": len(codes_not_indexed),
        "faiss_chunks": faiss_chunks,
        "coverage_pct": display_coverage_pct,
        "file_coverage_pct": file_coverage_pct,
        "effective_file_coverage_pct": effective_file_coverage_pct,
        "code_coverage_pct": code_coverage_pct,
        "healthy": effective_file_coverage_pct >= 95.0 and files_missing_disk == 0,
        "sample_not_indexed": files_not_indexed[:25],
        "sample_not_indexed_codes": codes_not_indexed[:25],
        "sample_extra_indexed": sorted(indexed_codes - catalog_codes)[:10],
    }
