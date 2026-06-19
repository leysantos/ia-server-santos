from __future__ import annotations

from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BdiConfig


class BdiCalculator:
    """Aplica BDI sobre custo unitário — determinístico."""

    def __init__(self, config: BdiConfig | None = None) -> None:
        self.config = config or BdiConfig()

    def apply_to_item(self, item: BudgetItem) -> None:
        if item.children:
            return
        if item.unit_cost <= 0 and item.unit_price > 0:
            item.unit_cost = item.unit_price
        if item.unit_cost <= 0:
            return

        item.bdi_rate = self.config.rate_com_desoneracao
        item.bdi_label = self.config.obra_type or self.config.label
        item.metadata = {
            **(item.metadata or {}),
            "bdi_obra_type": self.config.obra_type,
            "bdi_obra_label": self.config.obra_label,
            "bdi_rate_comd": self.config.rate_com_desoneracao,
            "bdi_rate_semd": self.config.rate_sem_desoneracao,
        }
        item.unit_price = self.config.price_with_bdi(item.unit_cost, with_relief=True)
        item.unit_price_semd = self.config.price_with_bdi(
            item.unit_cost_semd or item.unit_cost, with_relief=False
        )
        item._sync_effective_leaf()

    def apply_tree(self, root: BudgetItem) -> None:
        if root.children:
            for child in root.children:
                self.apply_tree(child)
            root.recompute_total()
        else:
            self.apply_to_item(root)
