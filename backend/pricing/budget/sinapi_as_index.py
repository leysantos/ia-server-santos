"""Cruzamento SEMINF ↔ SINAPI para tp2=AS (%AS > 0)."""

from __future__ import annotations

from typing import Any

from pricing.budget.tp2_as import AS_MARKER, composition_tp2_from_regional, merge_tp2


def build_sinapi_as_index(
    closed_rows: list[dict[str, Any]],
    *,
    uf: str,
) -> dict[str, str]:
    """Mapa código SINAPI → AS quando a composição tem %AS > 0 na UF."""
    uf = uf.upper()
    index: dict[str, str] = {}
    for row in closed_rows:
        code = str(row.get("code") or "").strip()
        if not code:
            continue
        reg = row.get("regional") or {}
        entry = reg.get(uf)
        pct = 0.0
        if isinstance(entry, dict):
            pct = max(
                float(entry.get("pct_as_comd") or 0),
                float(entry.get("pct_as_semd") or 0),
            )
        if merge_tp2("", pct) == AS_MARKER or str(row.get("tp2") or "").upper() == AS_MARKER:
            index[code] = AS_MARKER
    return index


def load_sinapi_as_index_for_period(
    *,
    year: int | str | None,
    month: int | str | None,
    uf: str,
) -> dict[str, str]:
    """Tenta carregar índice AS da base SINAPI do mesmo período (BR-YYYY-MM)."""
    if not year or not month:
        return {}
    try:
        y = int(year)
        m = int(month)
        ref = f"BR-{y}-{m:02d}"
        from pricing.budget.price_bank_store import PriceBankStore

        store = PriceBankStore.for_reference(ref)
        if not store.manifest_path.is_file():
            return {}
        return build_sinapi_as_index(store.load_closed(), uf=uf)
    except (TypeError, ValueError, OSError):
        return {}
