from __future__ import annotations

from typing import Any

from pricing.models.budget_item import BudgetItem, BudgetItemType


# Templates por escopo técnico (não acoplado a agentes/disciplinas).
_SCOPE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "alvenaria": [
        {
            "code_suffix": "01",
            "name": "Levantamento de alvenaria",
            "unit": "m²",
            "query": "alvenaria bloco estrutural",
            "item_type": BudgetItemType.COMPOSITION,
            "children": [
                {"code_suffix": "01", "name": "Bloco estrutural", "unit": "un", "query": "bloco estrutural ceramico", "item_type": BudgetItemType.INPUT},
                {"code_suffix": "02", "name": "Argamassa de assentamento", "unit": "m³", "query": "argamassa assentamento bloco", "item_type": BudgetItemType.INPUT},
                {"code_suffix": "03", "name": "Mão de obra pedreiro", "unit": "h", "query": "pedreiro alvenaria", "item_type": BudgetItemType.INPUT},
            ],
        },
        {
            "code_suffix": "02",
            "name": "Grauteamento",
            "unit": "m³",
            "query": "graute estrutural",
            "item_type": BudgetItemType.COMPOSITION,
        },
        {
            "code_suffix": "03",
            "name": "Vergas e contravergas",
            "unit": "m",
            "query": "verga concreto",
            "item_type": BudgetItemType.COMPOSITION,
        },
    ],
    "eletrica": [
        {"code_suffix": "01", "name": "Eletrodutos", "unit": "m", "query": "eletroduto pvc", "item_type": BudgetItemType.COMPOSITION},
        {"code_suffix": "02", "name": "Cabos elétricos", "unit": "m", "query": "cabo eletrico", "item_type": BudgetItemType.COMPOSITION},
        {"code_suffix": "03", "name": "Quadros de distribuição", "unit": "un", "query": "quadro distribuicao", "item_type": BudgetItemType.COMPOSITION},
        {"code_suffix": "04", "name": "Tomadas", "unit": "un", "query": "tomada 2p+t", "item_type": BudgetItemType.INPUT},
        {"code_suffix": "05", "name": "Interruptores", "unit": "un", "query": "interruptor simples", "item_type": BudgetItemType.INPUT},
        {"code_suffix": "06", "name": "Mão de obra eletricista", "unit": "h", "query": "eletricista instalacao", "item_type": BudgetItemType.INPUT},
    ],
    "estrutura": [
        {"code_suffix": "01", "name": "Escavação", "unit": "m³", "query": "escavacao manual", "item_type": BudgetItemType.COMPOSITION},
        {"code_suffix": "02", "name": "Concreto magro", "unit": "m³", "query": "concreto magro", "item_type": BudgetItemType.COMPOSITION},
        {"code_suffix": "03", "name": "Armadura de aço", "unit": "kg", "query": "aco ca-50", "item_type": BudgetItemType.INPUT},
        {"code_suffix": "04", "name": "Forma para concreto", "unit": "m²", "query": "forma madeira compensada", "item_type": BudgetItemType.COMPOSITION},
        {"code_suffix": "05", "name": "Concreto estrutural", "unit": "m³", "query": "concreto fck 25", "item_type": BudgetItemType.COMPOSITION},
    ],
    "passarela": [
        {
            "code": "1",
            "name": "SERVIÇOS PRELIMINARES",
            "children": [
                {"code_suffix": "01", "name": "Mobilização e desmobilização", "unit": "un", "query": "mobilizacao desmobilizacao container obra", "item_type": BudgetItemType.COMPOSITION},
                {"code_suffix": "02", "name": "Locação topográfica", "unit": "un", "query": "locacao convencional obra gabarito tabuas", "item_type": BudgetItemType.COMPOSITION},
            ],
        },
        {
            "code": "2",
            "name": "FUNDAÇÕES E APOIOS",
            "children": [
                {"code_suffix": "01", "name": "Estaca pré-moldada", "unit": "m", "query": "estaca pre moldada concreto secao quadrada", "item_type": BudgetItemType.COMPOSITION},
                {"code_suffix": "02", "name": "Bloco de coroamento", "unit": "m³", "query": "concretagem bloco coroamento fck", "item_type": BudgetItemType.COMPOSITION},
                {"code_suffix": "03", "name": "Concreto em bloco de apoio", "unit": "m³", "query": "concretagem bloco coroamento viga baldrame", "item_type": BudgetItemType.COMPOSITION},
                {"code_suffix": "04", "name": "Armadura bloco de apoio", "unit": "kg", "query": "armacao bloco coroamento aco ca-50", "item_type": BudgetItemType.INPUT},
            ],
        },
        {
            "code": "3",
            "name": "ESTRUTURA DA PASSARELA",
            "children": [
                {"code_suffix": "01", "name": "Estrutura metálica / tabuleiro", "unit": "m²", "query": "execucao montagem estrutura metalica", "item_type": BudgetItemType.COMPOSITION},
                {"code_suffix": "02", "name": "Piso antiderrapante", "unit": "m²", "query": "piso concreto armado acabamento", "item_type": BudgetItemType.COMPOSITION},
                {"code_suffix": "03", "name": "Guarda-corpo metálico", "unit": "m", "query": "guarda corpo metalico laje", "item_type": BudgetItemType.COMPOSITION},
            ],
        },
        {
            "code": "4",
            "name": "ACABAMENTOS E SINALIZAÇÃO",
            "children": [
                {"code_suffix": "01", "name": "Pintura de proteção", "unit": "m²", "query": "pintura tinta acabamento esmalte", "item_type": BudgetItemType.COMPOSITION},
                {"code_suffix": "02", "name": "Sinalização e acessibilidade", "unit": "un", "query": "placa de obra chapa galvanizada", "item_type": BudgetItemType.INPUT},
            ],
        },
    ],
}

_GROUP_LABELS: dict[str, str] = {
    "alvenaria": "ALVENARIA",
    "eletrica": "INSTALAÇÕES ELÉTRICAS",
    "estrutura": "ESTRUTURA",
    "passarela": "PASSARELA / PONTE",
    "preliminares": "SERVIÇOS PRELIMINARES",
    "geral": "ITENS DIVERSOS",
}


class StructureEngine:
    """Gera árvore de orçamento a partir de intenção estruturada (pós-LLM)."""

    def generate(self, intent: dict[str, Any]) -> list[BudgetItem]:
        dimensions = intent.get("dimensions") or {}
        etapas = intent.get("etapas") or []

        if etapas:
            return self._generate_from_etapas(etapas, dimensions, intent)

        scope = str(intent.get("scope") or intent.get("discipline") or "geral").lower()
        scope_key = self._resolve_scope_key(scope)
        group_code = self._group_code(scope_key)
        group_label = _GROUP_LABELS.get(scope_key, scope_key.title())

        dimensions = intent.get("dimensions") or {}
        default_qty = self._quantity_from_dimensions(dimensions, intent.get("unit"))
        if intent.get("_default_quantity"):
            default_qty = float(intent["_default_quantity"])

        explicit_items = intent.get("items") or []

        if scope_key == "passarela":
            computed = intent.get("computed_quantities") or {}
            return self._generate_passarela_roots(dimensions, computed, explicit_items)

        if explicit_items:
            group_code = self._group_code(scope_key)
            group_label = _GROUP_LABELS.get(scope_key, scope_key.title())
            children = [
                self._item_from_explicit(group_code, idx + 1, row, default_qty)
                for idx, row in enumerate(explicit_items)
            ]
            root = BudgetItem(
                code=group_code,
                name=group_label,
                level=0,
                quantity=0,
                unit="",
                unit_cost=0,
                unit_price=0,
                total_price=0,
                row_type="ETAPA",
                item_type=BudgetItemType.GROUP,
                children=children,
                metadata={"scope": scope_key, "auto_generated": True, "dimensions": dimensions},
            )
            return [root]

        template = _SCOPE_TEMPLATES.get(scope_key, [])
        children = [
            self._item_from_template(group_code, row, default_qty, level=1)
            for row in template
        ]
        root = BudgetItem(
            code=group_code,
            name=group_label,
            level=0,
            quantity=0,
            unit="",
            unit_cost=0,
            unit_price=0,
            total_price=0,
            row_type="ETAPA",
            item_type=BudgetItemType.GROUP,
            children=children,
            metadata={
                "scope": scope_key,
                "auto_generated": True,
                "dimensions": dimensions,
            },
        )
        return [root]

    def _generate_from_etapas(
        self,
        etapas: list[dict[str, Any]],
        dimensions: dict[str, Any],
        intent: dict[str, Any],
    ) -> list[BudgetItem]:
        """Árvore PPD a partir da WBS gerada pelo engenheiro (LLM)."""
        computed = intent.get("computed_quantities") or {}
        default_qty = float(computed.get("area") or computed.get("volume") or 1.0)
        roots: list[BudgetItem] = []

        for etapa in etapas:
            code = str(etapa.get("code") or len(roots) + 1)
            services = etapa.get("services") or []
            children = [
                self._item_from_explicit(
                    code,
                    idx + 1,
                    row,
                    float(row.get("quantity") or default_qty),
                )
                for idx, row in enumerate(services)
            ]
            roots.append(
                BudgetItem(
                    code=code,
                    name=str(etapa.get("name") or f"ETAPA {code}"),
                    level=0,
                    quantity=0,
                    unit="",
                    unit_cost=0,
                    unit_price=0,
                    total_price=0,
                    row_type="ETAPA",
                    item_type=BudgetItemType.GROUP,
                    children=children,
                    metadata={
                        "auto_generated": True,
                        "dimensions": dimensions,
                        "structure_source": intent.get("structure_source", "llm_wbs"),
                    },
                )
            )
        return roots

    def _resolve_scope_key(self, scope: str) -> str:
        if "passarela" in scope or "ponte" in scope or "tabuleiro" in scope:
            return "passarela"
        if "alven" in scope or "muro" in scope:
            return "alvenaria"
        if "bloco" in scope and "passarela" not in scope:
            return "alvenaria"
        if "eletri" in scope or "eletric" in scope:
            return "eletrica"
        if "estrut" in scope or "fund" in scope or "pilar" in scope:
            return "estrutura"
        if "prelim" in scope or "mobil" in scope:
            return "preliminares"
        return "geral"

    def _generate_passarela_roots(
        self,
        dimensions: dict[str, Any],
        computed: dict[str, float],
        explicit_items: list[dict[str, Any]],
    ) -> list[BudgetItem]:
        qty_overrides = self._passarela_quantity_overrides(dimensions, computed, explicit_items)
        roots: list[BudgetItem] = []
        for etapa in _SCOPE_TEMPLATES["passarela"]:
            code = etapa["code"]
            children = [
                self._item_from_template(
                    code,
                    row,
                    qty_overrides.get(self._item_key(row["name"]), 1.0),
                    level=1,
                )
                for row in etapa.get("children") or []
            ]
            roots.append(
                BudgetItem(
                    code=code,
                    name=etapa["name"],
                    level=0,
                    quantity=0,
                    unit="",
                    unit_cost=0,
                    unit_price=0,
                    total_price=0,
                    row_type="ETAPA",
                    item_type=BudgetItemType.GROUP,
                    children=children,
                    metadata={"auto_generated": True, "dimensions": dimensions},
                )
            )
        return roots

    def _item_key(self, name: str) -> str:
        return name.lower().strip()

    def _passarela_quantity_overrides(
        self,
        dimensions: dict[str, Any],
        computed: dict[str, float],
        explicit_items: list[dict[str, Any]],
    ) -> dict[str, float]:
        length = float(dimensions.get("length") or computed.get("length") or 10)
        width = float(dimensions.get("width") or 2)
        area = float(computed.get("area") or (length * width * 1.05))
        perimeter = float(computed.get("perimeter") or (2 * (length + width)))
        volume = float(computed.get("volume") or round(length * width * 0.3, 2))

        defaults: dict[str, float] = {
            self._item_key("Mobilização e desmobilização"): 1.0,
            self._item_key("Locação topográfica"): 1.0,
            self._item_key("Estaca pré-moldada"): round(length * 2, 1),
            self._item_key("Bloco de coroamento"): round(length * 0.4, 2),
            self._item_key("Concreto em bloco de apoio"): volume,
            self._item_key("Armadura bloco de apoio"): round(area * 4, 0),
            self._item_key("Estrutura metálica / tabuleiro"): area,
            self._item_key("Piso antiderrapante"): area,
            self._item_key("Guarda-corpo metálico"): perimeter,
            self._item_key("Pintura de proteção"): round(perimeter * 1.1, 1),
            self._item_key("Sinalização e acessibilidade"): 4.0,
        }

        for row in explicit_items:
            name = str(row.get("name") or "")
            if name and row.get("quantity"):
                defaults[self._item_key(name)] = float(row["quantity"])

        return defaults

    def _group_code(self, scope_key: str) -> str:
        mapping = {"preliminares": "01", "estrutura": "02", "alvenaria": "03", "eletrica": "04", "geral": "99"}
        return mapping.get(scope_key, "99")

    def _quantity_from_dimensions(self, dimensions: dict[str, Any], unit: str | None) -> float:
        length = float(dimensions.get("length") or 0)
        height = float(dimensions.get("height") or 0)
        width = float(dimensions.get("width") or 0)
        area = float(dimensions.get("area") or 0)
        volume = float(dimensions.get("volume") or 0)

        if volume > 0:
            return volume
        if area > 0:
            return area
        if length and height:
            return round(length * height, 2)
        if length and width:
            return round(length * width, 2)
        return float(dimensions.get("quantity") or 1)

    def _item_from_explicit(
        self,
        parent_code: str,
        index: int,
        row: dict[str, Any],
        default_qty: float,
    ) -> BudgetItem:
        code = str(row.get("code") or f"{parent_code}.{index:02d}")
        return BudgetItem(
            code=code,
            name=str(row.get("name") or row.get("query") or "Item"),
            level=2,
            quantity=float(row.get("quantity") or default_qty),
            unit=str(row.get("unit") or "un"),
            unit_cost=0,
            unit_price=0,
            total_price=0,
            row_type="S",
            parent_code=parent_code,
            item_type=BudgetItemType(row.get("item_type", BudgetItemType.COMPOSITION.value)),
            pricing_query=str(row.get("query") or row.get("name") or ""),
            calculation_note=str(row.get("calculation_note") or ""),
            metadata={"auto_generated": True},
        )

    def _item_from_template(
        self,
        parent_code: str,
        row: dict[str, Any],
        default_qty: float,
        level: int,
    ) -> BudgetItem:
        suffix = row["code_suffix"]
        code = f"{parent_code}.{suffix}"
        children_rows = row.get("children") or []
        children = [
            self._item_from_template(code, child, default_qty, level + 1)
            for child in children_rows
        ]
        unit = str(row.get("unit") or "un")
        qty = float(default_qty) if unit in ("m²", "m", "m³", "kg") else 1.0
        return BudgetItem(
            code=code,
            name=row["name"],
            level=level,
            quantity=qty,
            unit=unit,
            unit_cost=0,
            unit_price=0,
            total_price=0,
            row_type="S" if level > 0 else "ETAPA",
            parent_code=parent_code,
            item_type=row.get("item_type", BudgetItemType.COMPOSITION),
            pricing_query=row.get("query"),
            children=children,
            metadata={"auto_generated": True},
        )
