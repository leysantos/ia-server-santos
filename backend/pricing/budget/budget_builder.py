from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

PricingEventCallback = Callable[[dict[str, Any]], None]

from pricing.budget.bdi_calculator import BdiCalculator
from pricing.budget.structure_engine import StructureEngine
from pricing.core.base_service_resolver import BaseServiceResolver
from pricing.core.pricing_engine import PricingEngine
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.budget.bdi_types import detect_obra_type, normalize_obra_type
from pricing.models.budget_metadata import BdiConfig, BudgetProjectMetadata
from pricing.models.price_item import PriceItem


class BudgetBuilder:
    """
    Monta orçamento hierárquico: estrutura → pricing → totais.
    IA só fornece intent; preços vêm exclusivamente do PricingEngine.
    """

    def __init__(
        self,
        engine: PricingEngine | None = None,
        structure: StructureEngine | None = None,
        bdi: BdiConfig | None = None,
        project: BudgetProjectMetadata | None = None,
        resolver: BaseServiceResolver | None = None,
        use_llm_resolve: bool = True,
    ) -> None:
        self.engine = engine or PricingEngine()
        self.structure = structure or StructureEngine()
        self.resolver = resolver or BaseServiceResolver(engine=self.engine)
        self.use_llm_resolve = use_llm_resolve
        self.bdi = bdi or BdiConfig.from_obra_type(
            project.obra_type if project else None
        )
        self.project = project or BudgetProjectMetadata()
        if not self.project.obra_type:
            self.project.set_obra_type(self.bdi.obra_type)
        self._bdi_calc = BdiCalculator(self.bdi)

    def build(
        self,
        intent: dict[str, Any],
        source_priority: list[str] | None = None,
        on_pricing_event: PricingEventCallback | None = None,
    ) -> list[BudgetItem]:
        obra = normalize_obra_type(
            intent.get("obra_type")
            or detect_obra_type(
                text=str(intent.get("title") or ""),
                scope=str(intent.get("scope") or ""),
                orcamento=str(intent.get("orcamento") or ""),
                objeto=str(intent.get("objeto") or ""),
            )
        )
        self.bdi = BdiConfig.from_obra_type(obra)
        self.project.set_obra_type(obra)
        self._bdi_calc = BdiCalculator(self.bdi)

        tree = self.structure.generate(intent)
        scope = str(intent.get("scope") or intent.get("discipline") or "")
        budget_prompt = str(
            intent.get("_input_text") or intent.get("title") or intent.get("scope") or ""
        )
        for root in tree:
            self._price_subtree(
                root,
                source_priority,
                scope=scope,
                budget_prompt_text=budget_prompt,
                on_pricing_event=on_pricing_event,
            )
            self._bdi_calc.apply_tree(root)
            root.recompute_total()
        return tree

    def build_dict(
        self,
        intent: dict[str, Any],
        source_priority: list[str] | None = None,
    ) -> dict[str, Any]:
        items = self.build(intent, source_priority)
        total = sum(i.total_price for i in items)
        return {
            "items": [i.to_dict() for i in items],
            "grand_total": round(total, 2),
            "grand_total_semd": round(sum(i.total_price_semd for i in items), 2),
            "currency": "BRL",
            "project": self.project.to_dict(),
            "metadata": {
                "auto_generated": True,
                "source_priority": source_priority or [],
                "template": "PPD_MC_OR",
            },
        }

    def _price_subtree(
        self,
        item: BudgetItem,
        source_priority: list[str] | None,
        scope: str = "",
        budget_prompt_text: str = "",
        on_pricing_event: PricingEventCallback | None = None,
    ) -> None:
        if item.children:
            for child in item.children:
                self._price_subtree(
                    child,
                    source_priority,
                    scope=scope,
                    budget_prompt_text=budget_prompt_text,
                    on_pricing_event=on_pricing_event,
                )
            return

        if not item.pricing_query:
            return

        priority = source_priority or self.resolver.loaded_sources()
        detail = self.resolver.resolve_with_details(
            item.pricing_query,
            unit=item.unit,
            source_priority=priority,
            use_llm=self.use_llm_resolve,
            line_name=item.name,
            line_code=item.code,
            scope=scope,
            service_context=item.calculation_note or None,
            budget_prompt_text=budget_prompt_text or None,
        )
        if on_pricing_event:
            on_pricing_event(self._pricing_event_payload(item, detail))

        if detail.item:
            self._apply_price(item, detail.item, detail)
        else:
            item.metadata = {
                **(item.metadata or {}),
                "pricing_unresolved": True,
                "pricing_query": item.pricing_query,
                "pricing_method": detail.method,
                "pricing_score": detail.score,
                "pricing_candidates": detail.candidates[:3],
            }

    @staticmethod
    def _pricing_event_payload(item: BudgetItem, detail: Any) -> dict[str, Any]:
        selected = detail.item
        return {
            "line_name": item.name,
            "line_code": item.code,
            "query": item.pricing_query,
            "unit": item.unit,
            "resolved": selected is not None,
            "method": detail.method,
            "score": round(detail.score, 4),
            "faiss_available": detail.faiss_available,
            "selected_code": selected.code if selected else None,
            "selected_description": (selected.description[:80] if selected else None),
            "selected_price": selected.price if selected else None,
            "candidates": detail.candidates[:3],
            "llm_model": detail.llm_model,
            "llm_pool_size": getattr(detail, "llm_pool_size", 0),
        }

    def _apply_price(self, item: BudgetItem, price: PriceItem, detail: Any | None = None) -> None:
        price_sem = float((price.metadata or {}).get("price_sem_desoneracao") or price.price)
        template_name = item.name
        item.unit_cost = price.price
        item.unit_cost_semd = price_sem
        item.name = price.description
        if price.unit:
            item.unit = price.unit
        item.source_base = price.source.upper()
        item.source_code = price.code
        self._bdi_calc.apply_to_item(item)
        item.metadata = {
            **(item.metadata or {}),
            "line_template_name": template_name,
            "source_trace": [
                {
                    "base": price.source.upper(),
                    "code": price.code,
                    "description": price.description,
                    "version": price.metadata.get("version") if price.metadata else None,
                }
            ],
            "confidence": round(detail.score if detail else self.resolver.matcher.match_score(
                item.pricing_query or "", price.description, item.unit, price.unit
            ), 4),
            "pricing_method": detail.method if detail else "fuzzy",
            "pricing_candidates": (detail.candidates[:3] if detail else []),
            "auto_generated": True,
        }
        if item.item_type == BudgetItemType.GROUP and price.metadata.get("composition"):
            item.item_type = BudgetItemType.COMPOSITION
