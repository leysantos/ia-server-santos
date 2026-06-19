from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class BudgetItemType(str, Enum):
    GROUP = "group"
    COMPOSITION = "composition"
    INPUT = "input"


@dataclass
class BudgetItem:
    """
    Nó da árvore de orçamento — compatível com PPD MC/OR (ETAPA / S / MEMORIA).
    level: 0=ETAPA, 1+=subitens
    unit_cost: custo unitário sem BDI (SINAPI ComD)
    unit_price: preço unitário com BDI aplicado
    """

    code: str
    name: str
    level: int
    quantity: float
    unit: str
    unit_price: float
    total_price: float
    row_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_base: str = ""
    source_code: str = ""
    parent_code: Optional[str] = None
    item_type: BudgetItemType = BudgetItemType.COMPOSITION
    children: list["BudgetItem"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    pricing_query: Optional[str] = None
    row_type: str = ""
    unit_cost: float = 0.0
    unit_cost_semd: float = 0.0
    unit_price_semd: float = 0.0
    total_price_semd: float = 0.0
    bdi_rate: float = 0.2426
    bdi_label: str = "BDI1"
    calculation_note: str = ""

    def effective_total(self) -> float:
        """Menor total linha (ComD vs SemD) — regra administração pública."""
        stored = self.metadata.get("total_effective")
        if stored is not None:
            return float(stored)
        if self.total_price_semd > 0:
            return min(self.total_price, self.total_price_semd)
        return self.total_price

    def desoneracao_mode(self) -> str:
        """comd | semd — cenário mais vantajoso para a linha."""
        return str(self.metadata.get("desoneracao_mode") or "comd")

    def _sync_effective_leaf(self) -> None:
        """Define total_effective e modo após calcular ComD/SemD."""
        comd = round(self.quantity * self.unit_price, 2) if self.unit_price else self.total_price
        semd = round(self.quantity * self.unit_price_semd, 2) if self.unit_price_semd else self.total_price_semd
        self.total_price = comd
        self.total_price_semd = semd
        if semd > 0 and semd < comd:
            self.metadata["desoneracao_mode"] = "semd"
            self.metadata["total_effective"] = semd
            rate_semd = self.metadata.get("bdi_rate_semd")
            if rate_semd is not None:
                self.bdi_rate = float(rate_semd)
        else:
            self.metadata["desoneracao_mode"] = "comd"
            self.metadata["total_effective"] = comd

    def recompute_total(self) -> None:
        for child in self.children:
            if child.metadata.get("is_memory_row"):
                continue
            child.recompute_total()

        priced_children = [c for c in self.children if not c.metadata.get("is_memory_row")]
        if priced_children:
            self.total_price = round(sum(c.total_price for c in priced_children), 2)
            self.total_price_semd = round(sum(c.total_price_semd for c in priced_children), 2)
            self.metadata["total_effective"] = round(
                sum(c.effective_total() for c in priced_children), 2
            )
            comd_eff = self.metadata["total_effective"]
            if self.total_price_semd > 0 and self.total_price_semd < self.total_price:
                self.metadata["desoneracao_mode"] = "semd"
            else:
                self.metadata["desoneracao_mode"] = "comd"
        elif self.row_type != "MEMORIA" and not self.metadata.get("is_memory_row"):
            self._sync_effective_leaf()

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "code": self.code,
            "name": self.name,
            "level": self.level,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_cost": self.unit_cost,
            "unit_cost_semd": self.unit_cost_semd,
            "unit_price": self.unit_price,
            "unit_price_semd": self.unit_price_semd,
            "total_price": self.total_price,
            "total_price_semd": self.total_price_semd,
            "source_base": self.source_base,
            "source_code": self.source_code,
            "parent_code": self.parent_code,
            "item_type": self.item_type.value,
            "row_type": self.row_type,
            "bdi_rate": self.bdi_rate,
            "bdi_label": self.bdi_label,
            "calculation_note": self.calculation_note,
            "pricing_query": self.pricing_query,
            "metadata": self.metadata,
            "children": [c.to_dict() for c in self.children],
        }
