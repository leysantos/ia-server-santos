"""Listagem e busca de composições abertas (CPU) no price_bank."""

from __future__ import annotations

from typing import Any

from pricing.budget.price_bank_index import PriceBankIndex
from pricing.budget.price_bank_store import PriceBankStore


def _normalize_query(q: str | None) -> str:
    return (q or "").strip()


def _matches_query(code: str, description: str, query: str) -> bool:
    if not query:
        return True
    ql = query.lower()
    if ql in code.lower():
        return True
    return ql in (description or "").lower()


def _match_kind(code: str, query: str) -> str:
    ql = query.lower()
    if code.lower() == ql or code.lower().startswith(ql):
        return "code"
    return "description"


def _resolve_search_totals(
    code: str,
    raw: dict[str, Any],
    *,
    uf: str,
    closed_row: dict[str, Any] | None,
) -> tuple[float, float]:
    if closed_row:
        reg = (closed_row.get("regional") or {}).get(uf.upper())
        if reg:
            com = float(reg.get("comd") or reg.get("com") or 0)
            sem = float(reg.get("semd") or reg.get("sem") or com)
            return com, sem
        com = float(closed_row.get("price") or 0)
        sem = float(closed_row.get("price_sem_desoneracao") or com)
        return com, sem
    com = float(raw.get("total_price") or 0)
    sem = float(raw.get("total_price_sem") or com)
    return com, sem


def _search_summary_item(
    code: str,
    raw: dict[str, Any],
    *,
    query: str,
    uf: str,
    closed_by_code: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    closed_row = closed_by_code.get(code)
    total_com, total_sem = _resolve_search_totals(code, raw, uf=uf, closed_row=closed_row)
    desc = str(raw.get("description") or "")
    if not desc and closed_row:
        desc = str(closed_row.get("description") or "")
    unit = str(raw.get("unit") or (closed_row or {}).get("unit") or "")
    return {
        "code": code,
        "description": desc,
        "unit": unit,
        "total_price": total_com,
        "total_price_sem": total_sem,
        "items_count": len(raw.get("items") or []),
        "tp2": str(raw.get("tp2") or ""),
        "match_kind": _match_kind(code, query),
    }


def _sort_key(code: str, description: str, query: str) -> tuple[int, str, str]:
    if not query:
        return (2, code, description)
    ql = query.lower()
    if code.lower() == ql:
        return (0, code, description)
    if code.lower().startswith(ql):
        return (1, code, description)
    if ql in code.lower():
        return (2, code, description)
    return (3, code, description)


def list_open_compositions(
    reference: str | None,
    *,
    uf: str = "SP",
    q: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    ref = PriceBankIndex.resolve_reference(reference)
    store = PriceBankStore.for_reference(ref)
    raw_open = store.load_open()
    if not raw_open:
        return {
            "reference": ref,
            "uf": uf.upper(),
            "total": 0,
            "offset": max(0, offset),
            "limit": max(1, min(limit, 200)),
            "items": [],
        }

    query = _normalize_query(q)
    candidates: list[tuple[str, dict[str, Any]]] = []
    for code, raw in raw_open.items():
        desc = str(raw.get("description") or "")
        if not _matches_query(str(code), desc, query):
            continue
        candidates.append((str(code), raw))

    candidates.sort(key=lambda pair: _sort_key(pair[0], str(pair[1].get("description") or ""), query))

    total = len(candidates)
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    page = candidates[offset : offset + limit]

    items: list[dict[str, Any]] = []
    use_uf = uf.upper()
    for code, raw in page:
        comp = store.get_open_composition(code, uf=use_uf)
        if not comp:
            continue
        items.append(
            {
                "code": comp.get("code") or code,
                "description": comp.get("description") or raw.get("description") or "",
                "unit": comp.get("unit") or raw.get("unit") or "",
                "total_price": float(comp.get("total_price") or 0),
                "total_price_sem": float(
                    comp.get("total_price_sem") or comp.get("total_price") or 0
                ),
                "items_count": len(comp.get("items") or []),
                "tp2": comp.get("tp2") or "",
            }
        )

    return {
        "reference": ref,
        "uf": use_uf,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
    }


def search_open_compositions(
    query: str,
    *,
    reference: str | None = None,
    uf: str = "SP",
    limit: int = 20,
) -> dict[str, Any]:
    """Busca por código (exato/prefixo) ou trecho da descrição."""
    q = _normalize_query(query)
    if not q:
        return {"reference": PriceBankIndex.resolve_reference(reference), "uf": uf.upper(), "items": []}

    ref = PriceBankIndex.resolve_reference(reference)
    store = PriceBankStore.for_reference(ref)
    raw_open = store.load_open()
    if not raw_open:
        return {"reference": ref, "uf": uf.upper(), "items": []}

    limit = max(1, min(limit, 50))
    candidates: list[tuple[str, dict[str, Any]]] = []
    for code, raw in raw_open.items():
        desc = str(raw.get("description") or "")
        if not _matches_query(str(code), desc, q):
            continue
        candidates.append((str(code), raw))

    candidates.sort(key=lambda pair: _sort_key(pair[0], str(pair[1].get("description") or ""), q))
    use_uf = uf.upper()
    page = candidates[:limit]
    needed_codes = {code for code, _ in page}
    closed_by_code: dict[str, dict[str, Any]] = {}
    if needed_codes:
        for row in store.load_closed():
            c = str(row.get("code") or "")
            if c in needed_codes:
                closed_by_code[c] = row

    items = [
        _search_summary_item(code, raw, query=q, uf=use_uf, closed_by_code=closed_by_code)
        for code, raw in page
    ]

    return {"reference": ref, "uf": use_uf, "query": q, "items": items}
