from __future__ import annotations

from typing import Any

from pricing.models.budget_item import BudgetItem


class BudgetCalculator:
    """Recálculo determinístico + memória de cálculo (tipo BIM de orçamento)."""

    EDITABLE_FIELDS = frozenset({"quantity", "unit_price", "unit_cost", "name", "unit", "calculation_note"})

    def apply_cell_edit(
        self,
        root: BudgetItem,
        row_id: str,
        field: str,
        value: Any,
        code: str | None = None,
    ) -> tuple[BudgetItem | None, list[dict[str, Any]]]:
        if field not in self.EDITABLE_FIELDS:
            raise ValueError(f"Campo não editável: {field}")

        target = self._find_by_row_id(root, row_id)
        if target is None and code:
            target = self._find_by_code(root, code)
        if target is None:
            return None, []

        memory: list[dict[str, Any]] = []
        old_total = root.total_price

        if field == "name":
            val = str(value).strip()
            if target.row_type in ("ETAPA", "SUB-ETAPA"):
                val = val.upper()
            target.name = val
        elif field == "unit":
            target.unit = str(value)
        elif field == "quantity":
            target.quantity = float(value)
            memory.append(self._qty_memory(target))
        elif field == "unit_price":
            target.unit_price = float(value)
            memory.append(self._price_memory(target))
        elif field == "unit_cost":
            target.unit_cost = float(value)
            from pricing.budget.bdi_calculator import BdiCalculator
            BdiCalculator().apply_to_item(target)
            memory.append(self._price_memory(target))
        elif field == "calculation_note":
            target.calculation_note = str(value)
            target.name = str(value) if target.metadata.get("is_memory_row") else target.name
            memory.append({"code": target.code, "step": "memory_edit", "formula": str(value), "result": 0})

        self.recalc_tree(root)
        memory.append(
            {
                "step": "grand_total",
                "formula": "Σ grupos raiz",
                "before": round(old_total, 2),
                "after": round(root.total_price, 2),
            }
        )
        return target, memory

    def recalc_tree(self, item: BudgetItem) -> float:
        item.recompute_total()
        memory = self.build_calculation_memory(item)
        item.metadata = {**(item.metadata or {}), "calculation_memory": memory}
        return item.total_price

    def build_calculation_memory(self, root: BudgetItem) -> list[dict[str, Any]]:
        memory: list[dict[str, Any]] = []
        self._collect_memory(root, memory)
        return memory

    def flatten_rows(self, root: BudgetItem) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        self._flatten(root, rows, [0])
        return rows

    def _find_by_row_id(self, item: BudgetItem, row_id: str) -> BudgetItem | None:
        if item.row_id == row_id:
            return item
        for child in item.children:
            found = self._find_by_row_id(child, row_id)
            if found:
                return found
        return None

    def _find_by_code(self, item: BudgetItem, code: str) -> BudgetItem | None:
        if item.code == code:
            return item
        for child in item.children:
            found = self._find_by_code(child, code)
            if found:
                return found
        return None

    def _collect_memory(self, item: BudgetItem, memory: list[dict[str, Any]]) -> None:
        for child in item.children:
            self._collect_memory(child, memory)
        if item.children:
            child_sum = sum(c.total_price for c in item.children)
            memory.append(
                {
                    "code": item.code,
                    "name": item.name,
                    "step": "group_sum",
                    "formula": " + ".join(c.code for c in item.children),
                    "result": round(child_sum, 2),
                }
            )
        elif item.unit_price > 0 or item.quantity > 0:
            memory.append(self._line_memory(item))

    def _line_memory(self, item: BudgetItem) -> dict[str, Any]:
        return {
            "code": item.code,
            "name": item.name,
            "step": "line_total",
            "formula": f"{item.quantity} {item.unit} × R$ {item.unit_price:.2f}",
            "result": round(item.quantity * item.unit_price, 2),
        }

    def _qty_memory(self, item: BudgetItem) -> dict[str, Any]:
        return {
            "code": item.code,
            "step": "quantity_edit",
            "formula": f"qtd={item.quantity} × R$ {item.unit_price:.2f}",
            "result": round(item.quantity * item.unit_price, 2),
        }

    def _price_memory(self, item: BudgetItem) -> dict[str, Any]:
        return {
            "code": item.code,
            "step": "unit_price_edit",
            "formula": f"{item.quantity} × R$ {item.unit_price:.2f}",
            "result": round(item.quantity * item.unit_price, 2),
        }

    def _flatten(self, item: BudgetItem, rows: list[dict[str, Any]], index: list[int]) -> None:
        is_memory = item.metadata.get("is_memory_row") or item.row_type == "MEMORIA"
        index[0] += 1
        rows.append(
            {
                "row_id": item.row_id,
                "row_index": index[0],
                "code": item.code,
                "name": item.name,
                "level": item.level,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_cost": item.unit_cost,
                "unit_cost_semd": item.unit_cost_semd,
                "unit_price": item.unit_price,
                "unit_price_semd": item.unit_price_semd,
                "total_price": item.total_price,
                "total_price_semd": item.total_price_semd,
                "source_base": item.source_base,
                "source_code": item.source_code,
                "parent_code": item.parent_code,
                "item_type": item.item_type.value,
                "row_type": item.row_type,
                "bdi_rate": item.bdi_rate,
                "bdi_label": item.bdi_label,
                "calculation_note": item.calculation_note,
                "editable": item.level >= 1 and not is_memory and item.row_type == "S",
                "is_memory_row": is_memory,
                "total_effective": item.effective_total(),
                "desoneracao_mode": item.desoneracao_mode(),
                "pricing_query": item.pricing_query or "",
            }
        )
        for child in item.children:
            self._flatten(child, rows, index)
