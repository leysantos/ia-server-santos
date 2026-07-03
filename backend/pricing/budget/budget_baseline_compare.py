"""Comparação orçamento atual vs baseline congelada."""

from __future__ import annotations

from typing import Any


def _row_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows") or []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("code") or "")
        if not code or row.get("row_type") in ("ETAPA", "SUB-ETAPA", "GRUPO"):
            continue
        if row.get("children"):
            continue
        key = code
        out[key] = {
            "code": code,
            "name": row.get("name") or "",
            "quantity": float(row.get("quantity") or 0),
            "total": float(row.get("total_effective") or row.get("total_price") or 0),
        }
    return out


def compare_budget_payloads(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    base_total = float(baseline.get("grand_total") or 0)
    curr_total = float(current.get("grand_total") or 0)
    base_rows = _row_map(baseline)
    curr_rows = _row_map(current)

    all_codes = sorted(set(base_rows) | set(curr_rows))
    line_diffs: list[dict[str, Any]] = []
    for code in all_codes:
        b = base_rows.get(code)
        c = curr_rows.get(code)
        b_total = b["total"] if b else 0.0
        c_total = c["total"] if c else 0.0
        delta = round(c_total - b_total, 2)
        if abs(delta) < 0.01 and b and c:
            continue
        line_diffs.append(
            {
                "code": code,
                "name": (c or b or {}).get("name", ""),
                "baseline_total": round(b_total, 2),
                "current_total": round(c_total, 2),
                "delta": delta,
                "status": "added" if not b else ("removed" if not c else "changed"),
            }
        )

    return {
        "baseline_grand_total": round(base_total, 2),
        "current_grand_total": round(curr_total, 2),
        "delta_grand_total": round(curr_total - base_total, 2),
        "delta_pct": round((curr_total - base_total) / base_total * 100, 2) if base_total else None,
        "lines_changed": len(line_diffs),
        "line_diffs": line_diffs[:500],
    }
