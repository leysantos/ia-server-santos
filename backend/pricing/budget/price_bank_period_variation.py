"""Alertas de variação de preço entre períodos mensais do price_bank."""

from __future__ import annotations

import re
from typing import Any

from pricing.budget.price_bank_index import REF_PATTERN, PriceBankIndex
from pricing.budget.price_bank_store import PriceBankStore

DEFAULT_THRESHOLD = 0.30


def _ref_sort_key(reference: str) -> tuple[int, int]:
    m = REF_PATTERN.match(reference.replace("/", "-").upper())
    if not m:
        return (0, 0)
    return int(m.group(1)), int(m.group(2))


def reference_label(reference: str) -> str:
    m = REF_PATTERN.match(reference.replace("/", "-").upper())
    if m:
        return f"{m.group(2)}/{m.group(1)}"
    return reference


def resolve_previous_reference(reference: str) -> str | None:
    """Período imediatamente anterior importado no banco (ex.: BR-2026-04 → BR-2026-03)."""
    ref = reference.replace("/", "-").upper()
    if not ref.startswith("BR-"):
        ref = f"BR-{ref}"

    idx = PriceBankIndex.load()
    refs = sorted({r.reference.upper() for r in idx.references}, key=_ref_sort_key)
    if ref in refs:
        pos = refs.index(ref)
        if pos > 0:
            return refs[pos - 1]

    m = REF_PATTERN.match(ref)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if month == 1:
        year, month = year - 1, 12
    else:
        month -= 1
    candidate = f"BR-{year}-{month:02d}"
    if candidate in refs:
        return candidate
    store_root = PriceBankIndex.reference_dir(candidate)
    if (store_root / "manifest.json").is_file():
        return candidate
    return None


def _pct_change(current: float, previous: float) -> float | None:
    if previous <= 0 or current <= 0:
        return None
    return ((current - previous) / previous) * 100.0


def _short_desc(text: str, max_len: int = 48) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "…"


def compute_period_variation_warnings(
    composition: dict[str, Any],
    *,
    uf: str,
    reference: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """
    Compara composição atual com o mês anterior importado.
    Retorna avisos quando |variação| > threshold (default 30%).
    """
    prev_ref = resolve_previous_reference(reference)
    if not prev_ref:
        return {
            "previous_reference": None,
            "previous_label": None,
            "threshold_pct": round(threshold * 100, 1),
            "warnings": [],
        }

    code = str(composition.get("code") or "").strip()
    use_uf = (uf or composition.get("price_uf") or "SP").upper()

    try:
        prev_comp = PriceBankStore.for_reference(prev_ref).get_open_composition(code, uf=use_uf)
    except Exception:
        prev_comp = None

    if not prev_comp:
        return {
            "previous_reference": prev_ref,
            "previous_label": reference_label(prev_ref),
            "threshold_pct": round(threshold * 100, 1),
            "warnings": [],
        }

    warnings: list[dict[str, Any]] = []
    prev_label = reference_label(prev_ref)
    threshold_pct = threshold * 100.0

    for metric, cur_key, prev_key, label in (
        ("comd", "total_price", "total_price", "ComD"),
        ("semd", "total_price_sem", "total_price_sem", "SemD"),
    ):
        current = float(composition.get(cur_key) or 0)
        previous = float(prev_comp.get(prev_key) or 0)
        change = _pct_change(current, previous)
        if change is None or abs(change) <= threshold_pct:
            continue
        sign = "+" if change > 0 else ""
        warnings.append(
            {
                "kind": "composition_total",
                "metric": metric,
                "metric_label": label,
                "current": round(current, 2),
                "previous": round(previous, 2),
                "change_pct": round(change, 1),
                "message": (
                    f"Total {label} variou {sign}{change:.1f}% em relação a {prev_label} "
                    f"(de R$ {previous:,.2f} para R$ {current:,.2f})".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                ),
            }
        )

    prev_items = {
        str(i.get("code") or "").strip(): i for i in (prev_comp.get("items") or [])
    }
    for item in composition.get("items") or []:
        item_code = str(item.get("code") or "").strip()
        if not item_code or item_code not in prev_items:
            continue
        prev_item = prev_items[item_code]
        desc = _short_desc(str(item.get("description") or prev_item.get("description") or ""))

        for metric, cur_key, prev_key, label in (
            ("comd", "unit_price", "unit_price", "ComD"),
            ("semd", "unit_price_sem", "unit_price_sem", "SemD"),
        ):
            current = float(item.get(cur_key) or 0)
            previous = float(prev_item.get(prev_key) or prev_item.get("unit_price") or 0)
            change = _pct_change(current, previous)
            if change is None or abs(change) <= threshold_pct:
                continue
            sign = "+" if change > 0 else ""
            item_type = str(item.get("item_type") or "item")
            warnings.append(
                {
                    "kind": "item_unit_price",
                    "item_type": item_type,
                    "code": item_code,
                    "description": desc,
                    "metric": metric,
                    "metric_label": label,
                    "current": round(current, 2),
                    "previous": round(previous, 2),
                    "change_pct": round(change, 1),
                    "message": (
                        f"Variação {sign}{change:.1f}% em relação a {prev_label} no "
                        f"{item_type.replace('_', ' ')} {item_code} — {desc} ({label})"
                    ),
                }
            )

    warnings.sort(key=lambda w: abs(float(w.get("change_pct") or 0)), reverse=True)

    composition_warns = [w for w in warnings if w["kind"] == "composition_total"]
    item_by_code: dict[str, dict[str, Any]] = {}
    for w in warnings:
        if w["kind"] != "item_unit_price":
            continue
        code = str(w.get("code") or "")
        if not code:
            continue
        existing = item_by_code.get(code)
        if not existing or abs(float(w["change_pct"])) > abs(float(existing["change_pct"])):
            item_by_code[code] = w
    warnings = composition_warns + sorted(
        item_by_code.values(),
        key=lambda w: abs(float(w.get("change_pct") or 0)),
        reverse=True,
    )

    return {
        "previous_reference": prev_ref,
        "previous_label": prev_label,
        "threshold_pct": round(threshold_pct, 1),
        "warnings": warnings,
    }
