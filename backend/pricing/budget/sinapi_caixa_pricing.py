"""
Preços unitários SINAPI Caixa — espelha a fórmula da aba «Analítico com Custo».

INSUMO (SEM DESONERAÇÃO → ISD / COM DESONERAÇÃO → ICD / SEM ENCARGOS → ISE):
  1. preco_uf  — coluna da UF na aba de insumos (> 0)
  2. preco_regional_as — tabela auxiliar (colunas L/M/N; chave código_UF)
  3. preco_sp  — coluna SP na mesma aba

COMPOSICAO (CSD / CCD / CSE):
  PROCX na UF selecionada — sem fallback SP.
"""

from __future__ import annotations

from typing import Any

EncargoMode = str  # "semd" | "comd" | "ise"


def _price_from_regional_entry(
    entry: dict[str, Any] | float | int | None,
    *,
    mode: EncargoMode,
) -> float:
    if isinstance(entry, dict):
        if mode == "ise":
            val = entry.get("ise")
        elif mode == "semd":
            val = entry.get("semd") or entry.get("sem")
        else:
            val = entry.get("comd") or entry.get("com")
        if val is not None:
            return float(val)
    elif isinstance(entry, (int, float)):
        return float(entry)
    return 0.0


def build_insumo_regional_as(
    *,
    isd_reg: dict[str, float],
    icd_reg: dict[str, float],
    ise_reg: dict[str, float] | None = None,
) -> dict[str, dict[str, float]]:
    """
    Equivalente às colunas L/M/N (preco_regional_as) por UF.
    Quando a UF está zerada e SP tem preço, atribui SP (AS 100%).
    """
    ise_reg = ise_reg or {}
    sp_semd = float(isd_reg.get("SP") or 0)
    sp_comd = float(icd_reg.get("SP") or isd_reg.get("SP") or 0)
    sp_ise = float(ise_reg.get("SP") or isd_reg.get("SP") or 0)
    out: dict[str, dict[str, float]] = {}

    for uf in set(isd_reg) | set(icd_reg) | set(ise_reg):
        if uf == "SP":
            continue
        entry: dict[str, float] = {}
        semd_u = float(isd_reg.get(uf) or 0)
        comd_u = float(icd_reg.get(uf) or isd_reg.get(uf) or 0)
        ise_u = float(ise_reg.get(uf) or 0)
        if semd_u <= 0 and sp_semd > 0:
            entry["semd"] = sp_semd
        if comd_u <= 0 and sp_comd > 0:
            entry["comd"] = sp_comd
        if ise_u <= 0 and sp_ise > 0:
            entry["ise"] = sp_ise
        if entry:
            out[uf] = entry
    return out


def regional_as_from_merged_regional(regional: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Reconstrói regional_as a partir de regional {UF: {comd, semd}} (bases já importadas)."""
    isd: dict[str, float] = {}
    icd: dict[str, float] = {}
    for uf, entry in regional.items():
        if not isinstance(entry, dict):
            continue
        isd[uf] = float(entry.get("semd") or entry.get("sem") or 0)
        icd[uf] = float(entry.get("comd") or entry.get("com") or 0)
    return build_insumo_regional_as(isd_reg=isd, icd_reg=icd)


def resolve_insumo_unit_price_caixa(
    regional: dict[str, Any],
    uf: str,
    *,
    sem: bool = False,
    regional_as: dict[str, dict[str, float]] | None = None,
    fallback: float = 0.0,
) -> float:
    """
    IF preco_uf <> 0 → preco_uf
    ELIF ISNUMBER(preco_regional_as) → preco_regional_as
    ELSE → preco_sp
    """
    use_uf = uf.upper()
    mode: EncargoMode = "semd" if sem else "comd"
    preco_uf = _price_from_regional_entry(regional.get(use_uf), mode=mode)
    preco_sp = _price_from_regional_entry(regional.get("SP"), mode=mode)

    if preco_uf > 0:
        return preco_uf

    as_map = regional_as if regional_as is not None else regional_as_from_merged_regional(regional)
    as_entry = as_map.get(use_uf) or {}
    preco_as = float(as_entry.get(mode) or 0)
    if preco_as > 0:
        return preco_as

    if preco_sp > 0:
        return preco_sp
    return float(fallback or 0)


def resolve_composicao_unit_price_caixa(
    regional: dict[str, Any],
    uf: str,
    *,
    sem: bool = False,
    fallback: float = 0.0,
) -> float:
    """PROCX(CSD/CCD/CSE) — preço da UF apenas, sem fallback SP."""
    use_uf = uf.upper()
    mode: EncargoMode = "semd" if sem else "comd"
    price = _price_from_regional_entry(regional.get(use_uf), mode=mode)
    if price > 0:
        return price
    return float(fallback or 0)
