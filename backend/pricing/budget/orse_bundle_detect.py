"""Detecção de planilhas exportadas do ORSE 2 (Relatórios Cadastrais → Excel)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pricing.budget.seminf_bundle_detect import is_spreadsheet_file, normalize_filename_token

_IGNORE_SUFFIXES = {".identifier", ".tmp", ".bak", ".download", ".orse"}

# Planilhas de outras bases que contêm "composic" no nome e não devem ser importadas como ORSE.
_FOREIGN_STEM_MARKERS = (
    "seminf",
    "semiinf",
    "ppdseminf",
    "dpseminf",
    "tabelapreco",
    "modmcor",
    "mcor",
    "nivel",
    "sinapi",
    "sicro",
    "tcpo",
)


def _stem_norm(path: Path) -> str:
    return normalize_filename_token(path.stem)


def is_foreign_price_base_file(path: Path) -> bool:
    """True para SEMINF, SINAPI, SICRO, PPD etc. — não são exports ORSE."""
    stem = _stem_norm(path)
    if any(marker in stem for marker in _FOREIGN_STEM_MARKERS):
        return True
    if "composic" in stem and ("comd" in stem or "semd" in stem):
        return True
    return False


def is_orse_insumos_file(path: Path) -> bool:
    if is_foreign_price_base_file(path):
        return False
    stem = _stem_norm(path)
    return "insumo" in stem


def is_orse_composicoes_file(path: Path) -> bool:
    if is_foreign_price_base_file(path):
        return False
    stem = _stem_norm(path)
    if "insumo" in stem:
        return False
    return any(token in stem for token in ("composic", "servic", "cpu", "precounit", "orse"))


def is_orse_analitico_file(path: Path) -> bool:
    if is_foreign_price_base_file(path):
        return False
    stem = _stem_norm(path)
    return "analit" in stem or "estrutur" in stem


def classify_orse_bundle_files(
    paths: list[Path],
) -> dict[Literal["insumos", "composicoes", "analitico"], Path | None]:
    spreadsheets = [p for p in paths if is_spreadsheet_file(p) and not is_foreign_price_base_file(p)]
    return {
        "insumos": _pick_best([p for p in spreadsheets if is_orse_insumos_file(p)]),
        "composicoes": _pick_best([p for p in spreadsheets if is_orse_composicoes_file(p)]),
        "analitico": _pick_best([p for p in spreadsheets if is_orse_analitico_file(p)]),
    }


def _pick_best(candidates: list[Path]) -> Path | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.name.lower())[0]


def detect_orse_bundle_from_paths(
    paths: list[Path],
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Path] | dict[str, str]:
    """Retorna paths classificados ou {'error': mensagem}."""
    classified = classify_orse_bundle_files(paths)
    insumos = classified["insumos"]
    composicoes = classified["composicoes"]
    analitico = classified["analitico"]

    foreign = [p.name for p in paths if is_spreadsheet_file(p) and is_foreign_price_base_file(p)]
    if foreign and not composicoes:
        return {
            "error": (
                "Pasta contém planilhas SEMINF/SINAPI/PPD, não exports ORSE. "
                "No ORSE 2 (Windows): Relatórios → Cadastrais → exporte Composições, Insumos "
                "e (opcional) Analítico em Excel. "
                f"Arquivos ignorados: {', '.join(sorted(foreign)[:6])}"
            )
        }

    if not composicoes and not insumos:
        names = ", ".join(sorted({p.name for p in paths if is_spreadsheet_file(p)})[:8])
        return {
            "error": (
                "Nenhuma planilha ORSE reconhecida. Exporte do ORSE 2: "
                "Relatórios → Cadastrais → Insumos e Composições (Excel). "
                f"Arquivos vistos: {names or '(nenhuma planilha)'}"
            )
        }

    if not composicoes:
        return {
            "error": (
                "Planilha de composições/serviços não encontrada. "
                "Inclua export 'Composições' ou 'Serviços' (.xlsx)."
            )
        }

    out: dict[str, Path] = {"composicoes": composicoes}
    if insumos:
        out["insumos"] = insumos
    if analitico:
        out["analitico"] = analitico
    return out
