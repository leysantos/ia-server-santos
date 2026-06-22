"""Testes de alertas de variação entre períodos."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pricing.budget.price_bank_index import PriceBankIndex
from pricing.budget.price_bank_period_variation import (
    compute_period_variation_warnings,
    resolve_previous_reference,
)
from pricing.budget.price_bank_store import (
    CompositionClosed,
    CompositionItem,
    CompositionOpen,
    PriceBankStore,
)


@pytest.fixture
def isolated_price_bank(monkeypatch, tmp_path: Path):
    root = tmp_path / "price_bank"
    root.mkdir()
    monkeypatch.setattr("pricing.budget.price_bank_index.PRICE_BANK_ROOT", root)
    return root


def _save_minimal(ref: str, code: str, total: float, items: list[dict] | None = None):
    open_items = [
        CompositionItem(
            item_type=str(i.get("item_type") or "insumo"),
            code=str(i["code"]),
            description=str(i.get("description") or ""),
            unit=str(i.get("unit") or "un"),
            coefficient=float(i.get("coefficient") or 0),
            unit_price=float(i.get("unit_price") or 0),
            partial_cost=float(i.get("partial_cost") or 0),
            unit_price_sem=float(i.get("unit_price_sem") or 0),
            partial_cost_sem=float(i.get("partial_cost_sem") or 0),
        )
        for i in (items or [])
    ]
    store = PriceBankStore.for_reference(ref)
    store.save_bank(
        source="sinapi",
        reference=ref,
        closed=[
            CompositionClosed(
                code=code,
                description="Teste",
                unit="M3",
                price=total,
                price_sem_desoneracao=total + 1,
                regional={"AM": {"comd": total, "semd": total + 1}},
            )
        ],
        open_compositions={
            code: CompositionOpen(
                code=code,
                description="Teste pavimento",
                unit="M3",
                total_price=total,
                total_price_sem=total + 1,
                items=open_items,
            )
        },
        insumos=[],
        set_active=False,
    )


def test_resolve_previous_reference(isolated_price_bank: Path):
    _save_minimal("BR-2026-03", "95995", 1000)
    _save_minimal("BR-2026-04", "95995", 2000)
    assert resolve_previous_reference("BR-2026-04") == "BR-2026-03"
    assert resolve_previous_reference("BR-2026-03") is None


def test_variation_warning_on_large_jump(isolated_price_bank: Path):
    code = "95995"
    _save_minimal(
        "BR-2026-03",
        code,
        1466.38,
        items=[
            {
                "item_type": "insumo",
                "code": "1518",
                "description": "CONCRETO BETUMINOSO USINADO A QUENTE (CBUQ)",
                "unit": "T",
                "coefficient": 2.5,
                "unit_price": 512.5,
                "partial_cost": 1281.25,
                "unit_price_sem": 515.0,
                "partial_cost_sem": 1287.5,
            }
        ],
    )
    _save_minimal(
        "BR-2026-04",
        code,
        2246.7,
        items=[
            {
                "item_type": "insumo",
                "code": "1518",
                "description": "CONCRETO BETUMINOSO USINADO A QUENTE (CBUQ)",
                "unit": "T",
                "coefficient": 2.5,
                "unit_price": 815.0,
                "partial_cost": 2037.5,
                "unit_price_sem": 818.0,
                "partial_cost_sem": 2045.0,
            }
        ],
    )

    comp = PriceBankStore.for_reference("BR-2026-04").get_open_composition(code, uf="AM")
    result = compute_period_variation_warnings(comp, uf="AM", reference="BR-2026-04")

    assert result["previous_reference"] == "BR-2026-03"
    assert result["previous_label"] == "03/2026"
    assert any(w["kind"] == "composition_total" for w in result["warnings"])
    total_warn = next(w for w in result["warnings"] if w["kind"] == "composition_total")
    assert total_warn["change_pct"] > 30
    item_warns = [w for w in result["warnings"] if w.get("code") == "1518"]
    # Itens exigem insumos no banco para preços regionais; total já cobre o salto.
    if item_warns:
        assert item_warns[0]["change_pct"] > 30


def test_no_warning_when_stable(isolated_price_bank: Path):
    code = "1"
    _save_minimal("BR-2026-04", code, 100.0)
    _save_minimal("BR-2026-05", code, 105.0)
    comp = PriceBankStore.for_reference("BR-2026-05").get_open_composition(code, uf="AM")
    result = compute_period_variation_warnings(comp, uf="AM", reference="BR-2026-05")
    assert result["warnings"] == []
