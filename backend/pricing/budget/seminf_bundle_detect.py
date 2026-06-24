"""Detecção inteligente das 3 planilhas DP/SEMINF em pastas com muitos arquivos."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Literal

from pricing.budget.seminf_base_parser import resolve_reference_period, validate_seminf_bundle_period

_SPREADSHEET_EXT = {".xlsm", ".xlsx", ".xls"}
_IGNORE_SUFFIXES = {".identifier", ".tmp", ".bak", ".download"}


def normalize_filename_token(name: str) -> str:
    """Remove acentos, espaços e separadores — composição→composicao, preços→precos."""
    text = unicodedata.normalize("NFD", (name or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[_\-\s.]+", "", text)
    return text


def _stem_norm(path: Path) -> str:
    return normalize_filename_token(path.stem)


def is_spreadsheet_file(path: Path) -> bool:
    if not path.is_file():
        return False
    low = path.name.lower()
    if any(low.endswith(s) for s in _IGNORE_SUFFIXES):
        return False
    return path.suffix.lower() in _SPREADSHEET_EXT


def is_tabela_preco_file(path: Path) -> bool:
    stem = _stem_norm(path)
    return "tabela" in stem and ("preco" in stem or "precos" in stem)


def is_open_comd_file(path: Path) -> bool:
    stem = _stem_norm(path)
    if "composic" not in stem or "seminf" not in stem:
        return False
    return "comd" in stem and "semd" not in stem


def is_open_semd_file(path: Path) -> bool:
    stem = _stem_norm(path)
    if "composic" not in stem or "seminf" not in stem:
        return False
    return "semd" in stem


def _period_score(path: Path, year: int | None, month: int | None) -> int:
    if not year or not month:
        return 10
    file_year, file_month = resolve_reference_period(path, path.stem)
    if file_year == year and file_month == month:
        return 100
    if file_year == year:
        return 50
    return 10


def _pick_best(candidates: list[Path], year: int | None, month: int | None) -> Path | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: (-_period_score(p, year, month), p.name.lower()))[0]


def classify_seminf_bundle_files(
    paths: list[Path],
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict[Literal["closed", "open_comd", "open_semd"], Path | None]:
    spreadsheets = [p for p in paths if is_spreadsheet_file(p)]
    return {
        "closed": _pick_best([p for p in spreadsheets if is_tabela_preco_file(p)], year, month),
        "open_comd": _pick_best([p for p in spreadsheets if is_open_comd_file(p)], year, month),
        "open_semd": _pick_best([p for p in spreadsheets if is_open_semd_file(p)], year, month),
    }


def resolve_seminf_open_siblings(
    closed_path: Path,
    *,
    year: int | None = None,
    month: int | None = None,
) -> tuple[Path | None, Path | None]:
    """Localiza ComD/SemD na mesma pasta (ou subpastas) da Tabela de Preço."""
    folder = closed_path.parent
    if not folder.is_dir():
        return None, None
    all_files = [p for p in folder.rglob("*") if is_spreadsheet_file(p)]
    classified = classify_seminf_bundle_files(all_files, year=year, month=month)
    return classified.get("open_comd"), classified.get("open_semd")


def find_seminf_bundle_in_dir(
    folder: str | Path,
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Path]:
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Pasta não encontrada: {folder}")

    all_files = [p for p in folder.rglob("*") if is_spreadsheet_file(p)]
    classified = classify_seminf_bundle_files(all_files, year=year, month=month)

    missing = []
    if not classified["closed"]:
        missing.append("Tabela de Preço (tabela*preco*.xlsm)")
    if not classified["open_comd"]:
        missing.append("Composição SEMINF ComD (composic*seminf*comd*.xlsx)")
    if not classified["open_semd"]:
        missing.append("Composição SEMINF SemD (composic*seminf*semd*.xlsx)")
    if missing:
        raise FileNotFoundError(
            f"Pasta incompleta ({folder}) — {len(all_files)} planilha(s) encontrada(s). "
            f"Faltando: {', '.join(missing)}."
        )

    paths = [classified["closed"], classified["open_comd"], classified["open_semd"]]  # type: ignore[list-item]
    validate_seminf_bundle_period(paths, year=year, month=month)
    return {
        "closed": classified["closed"],  # type: ignore[return-value]
        "open_comd": classified["open_comd"],  # type: ignore[return-value]
        "open_semd": classified["open_semd"],  # type: ignore[return-value]
    }
