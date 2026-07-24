"""Testes — distinção entre código WBS e código de composição."""

from __future__ import annotations

from pricing.budget.composition_codes import is_itemization_code, normalize_composition_code
from pricing.budget.budget_export_tables import collect_export_composition_lookups
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.models.budget_metadata import BudgetProjectMetadata


def test_is_itemization_code():
    assert is_itemization_code("4.1.7")
    assert is_itemization_code("6.1")
    assert is_itemization_code("7.1.5")
    assert not is_itemization_code("97063")
    assert not is_itemization_code("C1234.SEMINF")
    assert not is_itemization_code("")


def test_normalize_composition_code():
    assert normalize_composition_code("97063") == "97063"
    assert normalize_composition_code("4.1.7") == ""
    assert normalize_composition_code("  88262  ") == "88262"


def test_collect_export_ignores_wbs_source_code():
    meta = BudgetProjectMetadata(
        name="Teste",
        price_bases=[
            {"source": "sinapi", "label": "SINAPI", "enabled": True, "reference": "BR-2026-05", "uf": "AM"}
        ],
    )
    wbs_service = BudgetItem(
        row_id="wbs1",
        code="4.1.7",
        name="Serviço sem matching",
        level=1,
        source_code="4.1.7",
        source_base="SINAPI",
        unit="m2",
        quantity=1.0,
        unit_cost=10.0,
        unit_price=12.0,
        total_price=12.0,
        item_type=BudgetItemType.COMPOSITION,
    )
    wbs_service.metadata["price_reference"] = "BR-2026-05"

    sinapi_service = BudgetItem(
        row_id="sin1",
        code="1.1.1",
        name="Serviço SINAPI",
        level=1,
        source_code="97063",
        source_base="SINAPI",
        unit="m2",
        quantity=1.0,
        unit_cost=100.0,
        unit_price=120.0,
        total_price=120.0,
        item_type=BudgetItemType.COMPOSITION,
    )
    sinapi_service.metadata["price_reference"] = "BR-2026-05"

    keys = collect_export_composition_lookups([wbs_service, sinapi_service], meta)
    assert keys == [("97063", "BR-2026-05", "AM")]
