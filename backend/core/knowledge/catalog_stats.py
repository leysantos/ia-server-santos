"""Agregações do catálogo para painéis de estatísticas (NBR/NR, edições)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from core.knowledge.metadata import read_metadata
from memory.nbr_catalog import parse_nbr_code
from memory.nbr_edition import parse_edition_year

_NORM_CONTENT_TYPES = frozenset({"nbrs", "nbr"})


def _parse_year(value: Any, filename: str, nbr_code: str | None) -> int | None:
    if value is not None:
        try:
            year = int(value)
            if 1950 <= year <= 2035:
                return year
        except (TypeError, ValueError):
            pass
    if filename:
        return parse_edition_year(filename, nbr_code)
    return None


def compute_norm_catalog_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Contagens de normas por vigência, tipo e edições distintas."""
    total = 0
    historical_count = 0
    current_count = 0
    without_year_count = 0
    nbr_count = 0
    nr_count = 0
    unknown_kind_count = 0
    code_years: dict[str, set[int]] = defaultdict(set)

    for row in rows:
        content_type = str(row.get("content_type") or "")
        if content_type not in _NORM_CONTENT_TYPES:
            continue

        path = Path(str(row.get("path") or ""))
        meta = read_metadata(path) if path.is_file() else {}
        meta = meta or {}

        filename = str(row.get("filename") or path.name or "")
        norm_code = (
            meta.get("nbr_code")
            or meta.get("norm_code")
            or parse_nbr_code(filename)
        )
        norm_code_str = str(norm_code) if norm_code else None

        norm_kind = str(meta.get("norm_kind") or "").upper()
        if norm_kind == "NR":
            nr_count += 1
        elif norm_kind == "NBR" or norm_code_str:
            nbr_count += 1
        else:
            unknown_kind_count += 1

        total += 1
        if meta.get("edition_outdated") is True:
            historical_count += 1
        else:
            current_count += 1

        year = _parse_year(meta.get("edition_year"), filename, norm_code_str)
        if year is None:
            without_year_count += 1
        elif norm_code_str:
            code_years[norm_code_str].add(year)

    multi_edition_codes = sum(1 for years in code_years.values() if len(years) > 1)
    unique_editions = sum(len(years) for years in code_years.values())
    distinct_years = len({year for years in code_years.values() for year in years})

    return {
        "total": total,
        "current_count": current_count,
        "historical_count": historical_count,
        "without_year_count": without_year_count,
        "nbr_count": nbr_count,
        "nr_count": nr_count,
        "unknown_kind_count": unknown_kind_count,
        "unique_codes": len(code_years),
        "multi_edition_codes": multi_edition_codes,
        "unique_editions": unique_editions,
        "distinct_years": distinct_years,
    }
