"""Resolução de CPU aberta com fallback entre referências do price_bank."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from pricing.budget.price_bank_index import PRICE_BANK_ROOT, PriceBankIndex
from pricing.budget.price_bank_store import CLOSED_NAME, PriceBankStore

_REF_ORDER = re.compile(r"^BR-(\d{4})-(\d{2})$")


def _code_keys(code: str) -> set[str]:
    raw = str(code or "").strip()
    if not raw:
        return set()
    keys = {raw, raw.upper(), raw.split("/")[0]}
    if raw.isdigit():
        keys.add(raw.zfill(5))
    return {k for k in keys if k}


def _closed_row_matches(row: dict[str, Any], keys: set[str]) -> bool:
    rc = str(row.get("code") or "").strip()
    if not rc:
        return False
    candidates = {rc, rc.upper(), rc.split("/")[0]}
    return bool(keys & candidates)


@lru_cache(maxsize=4096)
def find_references_with_closed_code(code: str) -> tuple[str, ...]:
    """Referências do price_bank que contêm o código na lista fechada."""
    keys = _code_keys(code)
    if not keys:
        return ()
    found: list[str] = []
    if not PRICE_BANK_ROOT.is_dir():
        return ()
    for child in sorted(PRICE_BANK_ROOT.iterdir()):
        if not child.is_dir() or not child.name.startswith("BR-"):
            continue
        closed_path = child / CLOSED_NAME
        if not closed_path.is_file():
            continue
        try:
            data = json.loads(closed_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if any(_closed_row_matches(row, keys) for row in data):
            found.append(child.name)
    return tuple(found)


def _reference_sort_key(ref: str) -> tuple[int, str]:
    m = _REF_ORDER.match(ref)
    if m:
        return (0, f"{m.group(1)}-{m.group(2)}")
    if "SICRO" in ref.upper():
        return (2, ref)
    if "ORSE" in ref.upper():
        return (3, ref)
    if "SEMINF" in ref.upper():
        return (4, ref)
    return (1, ref)


def _ordered_references(code: str, preferred: str | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(ref: str | None) -> None:
        if not ref or ref in seen:
            return
        seen.add(ref)
        ordered.append(ref)

    if preferred:
        add(preferred)
    for ref in sorted(find_references_with_closed_code(code), key=_reference_sort_key, reverse=True):
        add(ref)
    try:
        idx = PriceBankIndex.load()
        if idx.active_reference:
            add(idx.active_reference)
        for entry in idx.references:
            add(entry.reference)
    except Exception:
        pass
    return ordered


def _closed_fallback_detail(
    store: PriceBankStore,
    code: str,
    *,
    uf: str,
    reference: str,
) -> dict[str, Any] | None:
    keys = _code_keys(code)
    for row in store.load_closed():
        if not _closed_row_matches(row, keys):
            continue
        reg = (row.get("regional") or {}).get(uf.upper()) or {}
        com = float(reg.get("comd") or reg.get("com") or row.get("price") or 0)
        sem = float(reg.get("semd") or reg.get("sem") or row.get("price_sem_desoneracao") or com)
        return {
            "code": str(row.get("code") or code),
            "description": str(row.get("description") or ""),
            "unit": str(row.get("unit") or ""),
            "total_price": com,
            "total_price_sem": sem,
            "price_uf": uf.upper(),
            "items": [],
            "resolved_reference": reference,
            "closed_only": True,
        }
    return None


def resolve_composition_detail(
    code: str,
    *,
    uf: str = "SP",
    reference: str | None = None,
) -> dict[str, Any] | None:
    """
    Busca CPU aberta; se ausente na referência pedida, tenta outras bases
    onde o código existe (ex.: SINAPI 97063 consultado com ref SICRO).
    """
    use_uf = (uf or "SP").upper()
    preferred = PriceBankIndex.resolve_reference(reference) if reference else None

    for ref in _ordered_references(code, preferred):
        store = PriceBankStore.for_reference(ref)
        comp = store.get_open_composition(code, uf=use_uf)
        if comp:
            out = dict(comp)
            out["resolved_reference"] = ref
            if preferred and ref != preferred:
                out["reference_fallback"] = True
            return out
        closed_only = _closed_fallback_detail(store, code, uf=use_uf, reference=ref)
        if closed_only:
            if preferred and ref != preferred:
                closed_only["reference_fallback"] = True
            return closed_only

    return None
