"""Aplica preços regionais (todas UFs) a composições abertas."""

from __future__ import annotations

from typing import Any


def _classify_composicao(code: str, item_type: str) -> bool:
    t = (item_type or "").lower()
    return "compos" in t or t == "composicao"


def _uf_price(reg: dict[str, Any], uf: str, *, sem: bool, fallback: float = 0.0) -> float:
    """Lê preço de regional[UF] = {comd, semd}; fallback se UF ausente."""
    entry = reg.get(uf)
    if isinstance(entry, dict):
        key = "semd" if sem else "comd"
        val = entry.get(key) or entry.get("sem" if sem else "com")
        if val is not None:
            return float(val)
    elif isinstance(entry, (int, float)):
        return float(entry)
    return float(fallback or 0)


def apply_uf_to_open_composition(
    raw: dict[str, Any],
    *,
    uf: str,
    closed_rows: list[dict[str, Any]],
    insumo_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Recalcula preços unitários/parciais e totais para a UF informada."""
    uf = uf.upper()
    closed_by_code = {str(r.get("code", "")).strip(): r for r in closed_rows}
    insumo_by_code = {str(r.get("code", "")).strip(): r for r in insumo_rows}

    def lookup(code: str, item_type: str, sem: bool) -> float:
        if _classify_composicao(code, item_type):
            row = closed_by_code.get(code)
            if row:
                reg = row.get("regional") or {}
                if uf in reg:
                    return _uf_price(
                        reg,
                        uf,
                        sem=sem,
                        fallback=float(row.get("price_sem_desoneracao" if sem else "price") or 0),
                    )
                return float(
                    row.get("price_sem_desoneracao" if sem else "price") or 0
                )
            return 0.0
        row = insumo_by_code.get(code)
        if row:
            reg = row.get("regional") or {}
            if uf in reg:
                return _uf_price(
                    reg,
                    uf,
                    sem=sem,
                    fallback=float(row.get("price_sem_desoneracao" if sem else "price") or 0),
                )
            return float(row.get("price_sem_desoneracao" if sem else "price") or 0)
        return 0.0

    items_out: list[dict[str, Any]] = []
    for item in raw.get("items") or []:
        code = str(item.get("code") or "").strip()
        coef = float(item.get("coefficient") or 0)
        item_type = str(item.get("item_type") or "")
        unit_com = lookup(code, item_type, sem=False)
        unit_sem = lookup(code, item_type, sem=True)
        partial_com = round(coef * unit_com, 6) if coef and unit_com else 0.0
        partial_sem = round(coef * unit_sem, 6) if coef and unit_sem else 0.0
        items_out.append(
            {
                **item,
                "unit_price": unit_com,
                "partial_cost": partial_com,
                "unit_price_sem": unit_sem,
                "partial_cost_sem": partial_sem,
            }
        )

    code = str(raw.get("code") or "").strip()
    closed = closed_by_code.get(code) or {}
    reg = closed.get("regional") or {}
    if uf in reg:
        total_com = _uf_price(reg, uf, sem=False, fallback=float(closed.get("price") or 0))
        total_sem = _uf_price(
            reg,
            uf,
            sem=True,
            fallback=float(closed.get("price_sem_desoneracao") or total_com),
        )
    else:
        total_com = float(closed.get("price") or raw.get("total_price") or 0)
        total_sem = float(closed.get("price_sem_desoneracao") or raw.get("total_price_sem") or total_com)

    analytical_com = round(sum(float(i.get("partial_cost") or 0) for i in items_out), 2)
    analytical_sem = round(
        sum(float(i.get("partial_cost_sem") or i.get("partial_cost") or 0) for i in items_out),
        2,
    )

    return {
        **raw,
        "items": items_out,
        "total_price": total_com,
        "total_price_sem": total_sem,
        "price_uf": uf,
        "analytical_total_com": analytical_com,
        "analytical_total_sem": analytical_sem,
        "available_ufs": sorted(
            {
                u
                for row in closed_rows
                for u in (row.get("regional") or {}).keys()
            }
            | {
                u
                for row in insumo_rows
                for u in (row.get("regional") or {}).keys()
            }
        ),
    }
