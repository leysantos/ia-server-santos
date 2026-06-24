"""Unificação tp2 (SEMINF) e %AS (SINAPI Caixa) — ambos marcam AS = São Paulo."""

from __future__ import annotations

from typing import Any

AS_MARKER = "AS"


def tp2_from_pct_as(pct_as: float) -> str:
    try:
        return AS_MARKER if float(pct_as or 0) > 0 else ""
    except (TypeError, ValueError):
        return ""


def merge_tp2(existing: str, pct_as: float) -> str:
    if str(existing or "").strip().upper() == AS_MARKER:
        return AS_MARKER
    return tp2_from_pct_as(pct_as)


def composition_tp2_from_regional(
    regional: dict[str, Any],
    *,
    uf: str | None = None,
) -> str:
    """tp2=AS se a composição tiver %AS > 0 na UF ou em qualquer UF."""
    if uf:
        entry = regional.get(uf.upper())
        if isinstance(entry, dict):
            pct = max(
                float(entry.get("pct_as_comd") or entry.get("pct_as") or 0),
                float(entry.get("pct_as_semd") or entry.get("pct_as") or 0),
            )
            if tp2_from_pct_as(pct):
                return AS_MARKER
    for entry in regional.values():
        if not isinstance(entry, dict):
            continue
        pct = max(
            float(entry.get("pct_as_comd") or entry.get("pct_as") or 0),
            float(entry.get("pct_as_semd") or entry.get("pct_as") or 0),
        )
        if tp2_from_pct_as(pct):
            return AS_MARKER
    return ""


def apply_tp2_to_items(
    items: list[dict[str, Any]],
    *,
    composition_tp2: str,
    pct_as: float,
) -> list[dict[str, Any]]:
    """Propaga tp2=AS para itens quando composição ou %AS da UF indicam São Paulo."""
    comp_as = merge_tp2(composition_tp2, pct_as)
    out: list[dict[str, Any]] = []
    for item in items:
        item_tp2 = merge_tp2(str(item.get("tp2") or ""), pct_as)
        if not item_tp2 and comp_as == AS_MARKER:
            item_tp2 = AS_MARKER
        out.append({**item, "tp2": item_tp2})
    return out
