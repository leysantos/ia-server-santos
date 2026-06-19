"""Testes seleção automática menor custo ComD/SemD."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.bdi_calculator import BdiCalculator
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.models.budget_metadata import BdiConfig


def test_apply_minimum_comd_when_cheaper():
    bdi = BdiCalculator(BdiConfig.from_obra_type("RF"))
    item = BudgetItem(
        code="1.1",
        name="Serviço",
        level=1,
        quantity=10,
        unit="M2",
        unit_cost=100.0,
        unit_cost_semd=120.0,
        unit_price=0,
        total_price=0,
        row_type="S",
        item_type=BudgetItemType.COMPOSITION,
    )
    bdi.apply_to_item(item)
    assert item.desoneracao_mode() == "comd"
    assert item.effective_total() == item.total_price


def test_apply_minimum_semd_when_cheaper():
    bdi = BdiCalculator(BdiConfig.from_obra_type("RF"))
    item = BudgetItem(
        code="1.2",
        name="Serviço caro ComD",
        level=1,
        quantity=10,
        unit="MES",
        unit_cost=200.0,
        unit_cost_semd=80.0,
        unit_price=0,
        total_price=0,
        row_type="S",
        item_type=BudgetItemType.COMPOSITION,
    )
    bdi.apply_to_item(item)
    assert item.desoneracao_mode() == "semd"
    assert item.effective_total() == item.total_price_semd
    assert item.effective_total() < item.total_price
