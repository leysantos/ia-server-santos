"""Aplica preços regionais (todas UFs) a composições abertas."""

from __future__ import annotations

from typing import Any

from pricing.budget.tp2_as import apply_tp2_to_items, merge_tp2


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


def _uf_pct_as(reg: dict[str, Any], uf: str, *, sem: bool) -> float:
    entry = reg.get(uf)
    if isinstance(entry, dict):
        key = "pct_as_semd" if sem else "pct_as_comd"
        val = entry.get(key)
        if val is not None:
            return float(val)
    return 0.0


def _resolve_display_totals(
    *,
    raw: dict[str, Any],
    closed_com: float,
    closed_sem: float,
    analytical_com: float,
    analytical_sem: float,
) -> tuple[float, float]:
    """
    CPU analítica quando a composição aberta foi recalculada (fork SINAPI) e diverge
    do sintético regional copiado da Tabela de Preço fonte.
    """
    stored_com = float(raw.get("total_price") or 0)
    stored_sem = float(raw.get("total_price_sem") or stored_com)
    if analytical_com <= 0:
        return closed_com, closed_sem
    refreshed = stored_com > 0 and abs(stored_com - closed_com) > 0.05
    if refreshed:
        return analytical_com, analytical_sem if analytical_sem > 0 else closed_sem
    return closed_com, closed_sem


def apply_uf_to_open_composition(
    raw: dict[str, Any],
    *,
    uf: str,
    closed_rows: list[dict[str, Any]],
    insumo_rows: list[dict[str, Any]],
    labor_charges: dict[str, Any] | None = None,
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
        stored_unit_com = float(item.get("unit_price") or 0)
        stored_unit_sem = float(item.get("unit_price_sem") or stored_unit_com)
        stored_partial_com = float(item.get("partial_cost") or 0)
        stored_partial_sem = float(item.get("partial_cost_sem") or stored_partial_com)

        unit_com = lookup(code, item_type, sem=False)
        unit_sem = lookup(code, item_type, sem=True)
        if unit_com <= 0 and stored_unit_com > 0:
            unit_com = stored_unit_com
        if unit_sem <= 0 and stored_unit_sem > 0:
            unit_sem = stored_unit_sem

        if coef and unit_com:
            partial_com = round(coef * unit_com, 6)
        elif stored_partial_com > 0:
            partial_com = stored_partial_com
        else:
            partial_com = 0.0

        if coef and unit_sem:
            partial_sem = round(coef * unit_sem, 6)
        elif stored_partial_sem > 0:
            partial_sem = stored_partial_sem
        else:
            partial_sem = partial_com

        items_out.append(
            {
                **item,
                "unit_price": unit_com,
                "partial_cost": partial_com,
                "unit_price_sem": unit_sem,
                "partial_cost_sem": partial_sem,
                "classificacao": item.get("classificacao")
                or (insumo_by_code.get(code) or {}).get("classificacao", ""),
                "origem_preco": item.get("origem_preco")
                or (insumo_by_code.get(code) or {}).get("origem_preco", ""),
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

    total_com, total_sem = _resolve_display_totals(
        raw=raw,
        closed_com=total_com,
        closed_sem=total_sem,
        analytical_com=analytical_com,
        analytical_sem=analytical_sem,
    )

    grupo = str(raw.get("grupo") or closed.get("grupo") or "")
    pct_as_comd = _uf_pct_as(reg, uf, sem=False) if reg else 0.0
    pct_as_semd = _uf_pct_as(reg, uf, sem=True) if reg else 0.0
    pct_as_uf = max(pct_as_comd, pct_as_semd)
    comp_tp2 = merge_tp2(str(raw.get("tp2") or closed.get("tp2") or ""), pct_as_uf)
    items_out = apply_tp2_to_items(items_out, composition_tp2=comp_tp2, pct_as=pct_as_uf)

    labor = (labor_charges or {}).get(uf) or {}
    labor_out: dict[str, Any] = {}
    if labor:
        labor_out = {
            "localidade": labor.get("localidade", ""),
            "horista_comd": float(labor.get("horista_comd") or 0),
            "mensalista_comd": float(labor.get("mensalista_comd") or 0),
            "horista_semd": float(labor.get("horista_semd") or 0),
            "mensalista_semd": float(labor.get("mensalista_semd") or 0),
        }

    return {
        **raw,
        "items": items_out,
        "total_price": total_com,
        "total_price_sem": total_sem,
        "price_uf": uf,
        "grupo": grupo,
        "tp2": comp_tp2,
        "pct_as_comd": pct_as_comd,
        "pct_as_semd": pct_as_semd,
        "labor_charges": labor_out,
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
