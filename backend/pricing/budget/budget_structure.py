"""Manipulação manual da árvore WBS (etapas, sub-etapas e serviços)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from pricing.budget.bdi_calculator import BdiCalculator
from pricing.budget.budget_calculator import BudgetCalculator
from pricing.budget.ppd_layout import ROW_TYPE_ETAPA, ROW_TYPE_SERVICO, ROW_TYPE_SUB_ETAPA
from pricing.core.price_query import build_price_request
from pricing.core.pricing_engine import PricingEngine
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.models.price_item import PriceItem

_GROUP_TYPES = frozenset({ROW_TYPE_ETAPA, ROW_TYPE_SUB_ETAPA})


def normalize_group_name(name: str) -> str:
    return name.strip().upper()

_UNIT_ALIASES: dict[str, str] = {
    "mes": "MES",
    "mês": "MES",
    "meses": "MES",
    "m": "M",
    "m.": "M",
    "ml": "M",
    "m linear": "M",
    "h": "H",
    "hora": "H",
    "horas": "H",
    "un": "UN",
    "und": "UN",
    "unidade": "UN",
    "m2": "M2",
    "m²": "M2",
    "m3": "M3",
    "m³": "M3",
    "kg": "KG",
    "t": "T",
    "ton": "T",
    "m3xkm": "M3XKM",
    "m³/km": "M3XKM",
    "m3/km": "M3XKM",
    "m³xkm": "M3XKM",
    "txkm": "TXKM",
    "t/km": "TXKM",
    "t x km": "TXKM",
    "km": "KM",
    "l": "L",
    "vb": "VB",
    "ch": "CH",
    "cm": "CM",
    "dm3": "DM3",
}

_UNIT_PAREN_RE = re.compile(
    r"^\(([^)]+)\)\s*|\s*\(([^)]+)\)\s*$",
    re.IGNORECASE,
)


def normalize_unit_hint(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "")
    if key in _UNIT_ALIASES:
        return _UNIT_ALIASES[key]
    upper = raw.strip().upper().replace(" ", "")
    return upper


def _parse_float_br(raw: str) -> float | None:
    s = raw.strip()
    if not s:
        return None
    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except ValueError:
        return None


def _is_numeric_token(raw: str) -> bool:
    return _parse_float_br(raw) is not None


_QTY_BRACKET_RE = re.compile(r"^\[([\d.,]+)\]\s*")
_QTY_X_RE = re.compile(r"\s*[x×]\s*([\d.,]+)\s*$", re.IGNORECASE)
_QTY_COLON_RE = re.compile(r":\s*([\d.,]+)\s*$")


def _parse_paren_qty_unit(content: str) -> tuple[float | None, str | None]:
    """Interpreta conteúdo entre parênteses: unidade, quantidade ou quantidade+unidade."""
    raw = content.strip()
    if not raw:
        return None, None

    combo = re.match(r"^([\d.,]+)\s+(.+)$", raw)
    if combo:
        qty = _parse_float_br(combo.group(1))
        unit_raw = combo.group(2).strip()
        if qty is not None and unit_raw:
            return qty, normalize_unit_hint(unit_raw)

    compact = re.match(r"^([\d.,]+)([a-zA-ZÀ-ÿ²³/.]+)$", raw)
    if compact:
        qty = _parse_float_br(compact.group(1))
        unit_raw = compact.group(2).strip()
        unit_key = unit_raw.lower().replace(" ", "")
        if qty is not None and unit_key in _UNIT_ALIASES:
            return qty, normalize_unit_hint(unit_raw)

    if _is_numeric_token(raw):
        return _parse_float_br(raw), None

    unit = normalize_unit_hint(raw)
    if unit:
        return None, unit
    return None, None


def _strip_one_paren_hint(text: str) -> tuple[str, float | None, str | None]:
    m = _UNIT_PAREN_RE.search(text)
    if not m:
        return text, None, None
    inner = (m.group(1) or m.group(2) or "").strip()
    remaining = _UNIT_PAREN_RE.sub("", text, count=1).strip()
    qty, unit = _parse_paren_qty_unit(inner)
    return remaining, qty, unit


def _extract_paren_hints(text: str, *, max_passes: int = 6) -> tuple[str, float | None, str | None]:
    """Remove grupos entre parênteses no início/fim e acumula quantidade e unidade."""
    current = text.strip()
    quantity: float | None = None
    unit: str | None = None

    for _ in range(max_passes):
        next_text, pq, pu = _strip_one_paren_hint(current)
        if next_text == current:
            break
        current = next_text
        if pq is not None:
            quantity = pq
        if pu is not None:
            unit = pu

    return current.strip(), quantity, unit


def parse_term_with_unit(raw: str) -> tuple[str, str | None]:
    """Extrai unidade entre parênteses no início ou fim: (mês) engenheiro civil."""
    query, _, unit = _extract_paren_hints(raw)
    return query, unit


def parse_term_hints(raw: str) -> tuple[str, str | None, float | None]:
    """Extrai query, unidade e quantidade individual do termo de composição."""
    text = raw.strip()
    quantity: float | None = None
    unit: str | None = None

    m = _QTY_BRACKET_RE.match(text)
    if m:
        quantity = _parse_float_br(m.group(1))
        text = text[m.end() :].strip()

    text, pq, pu = _extract_paren_hints(text)
    if pq is not None:
        quantity = pq
    if pu is not None:
        unit = pu

    m = _QTY_X_RE.search(text)
    if m:
        if quantity is None:
            quantity = _parse_float_br(m.group(1))
        text = text[: m.start()].strip()

    m = _QTY_COLON_RE.search(text)
    if m:
        if quantity is None:
            quantity = _parse_float_br(m.group(1))
        text = text[: m.start()].strip()

    return text.strip(), unit, quantity


def _next_etapa_code(roots: list[BudgetItem]) -> str:
    used = {int(r.code) for r in roots if r.code.isdigit()}
    n = 1
    while n in used:
        n += 1
    return str(n)


def _next_subetapa_code(parent: BudgetItem) -> str:
    subs = [c for c in parent.children if c.row_type == ROW_TYPE_SUB_ETAPA]
    used: set[int] = set()
    prefix = f"{parent.code}."
    for sub in subs:
        if sub.code.startswith(prefix):
            tail = sub.code[len(prefix) :].split(".")[0]
            if tail.isdigit():
                used.add(int(tail))
    n = 1
    while n in used:
        n += 1
    return f"{parent.code}.{n}"


def _next_service_code(container: BudgetItem) -> str:
    services = [c for c in container.children if c.row_type == ROW_TYPE_SERVICO]
    used: set[int] = set()
    prefix = f"{container.code}."
    for svc in services:
        if svc.code.startswith(prefix):
            tail = svc.code[len(prefix) :].split(".")[0]
            if tail.isdigit():
                used.add(int(tail))
    n = 1
    while n in used:
        n += 1
    return f"{container.code}.{n}"


def find_item(
    roots: list[BudgetItem],
    *,
    row_id: str | None = None,
    code: str | None = None,
) -> tuple[BudgetItem | None, BudgetItem | None, list[BudgetItem]]:
    def walk(
        nodes: list[BudgetItem],
        parent: BudgetItem | None,
    ) -> tuple[BudgetItem | None, BudgetItem | None, list[BudgetItem]] | None:
        for node in nodes:
            if (row_id and node.row_id == row_id) or (code and node.code == code):
                siblings = parent.children if parent else roots
                return node, parent, siblings
            found = walk(node.children, node)
            if found:
                return found
        return None

    result = walk(roots, None)
    return result if result else (None, None, roots)


def find_group(roots: list[BudgetItem], group_code: str) -> BudgetItem | None:
    item, _, _ = find_item(roots, code=group_code)
    if item and item.row_type in _GROUP_TYPES:
        return item
    return None


def find_etapa(roots: list[BudgetItem], etapa_code: str) -> BudgetItem | None:
    return find_group(roots, etapa_code)


def split_composition_prompt(text: str) -> list[str]:
    parts = re.split(r"[,;\n]+|\s+e\s+", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


_UNIT_PROMPT_LABELS: dict[str, str] = {
    "MES": "mes",
    "H": "h",
    "M": "m",
    "M2": "m²",
    "M3": "m³",
    "M3XKM": "m³/km",
    "TXKM": "t/km",
    "UN": "un",
    "KG": "kg",
    "T": "t",
    "KM": "km",
    "L": "l",
    "VB": "vb",
    "CH": "ch",
    "CM": "cm",
    "DM3": "dm³",
}


def _unit_prompt_label(unit: str) -> str:
    key = (unit or "").strip().upper().replace(" ", "")
    if key in _UNIT_PROMPT_LABELS:
        return _UNIT_PROMPT_LABELS[key]
    return (unit or "").strip().lower()


def service_to_prompt_term(item: BudgetItem) -> str:
    query = (item.pricing_query or item.name or "").strip()
    query = query.split("\n")[0].strip()
    unit_label = _unit_prompt_label(item.unit or "")
    qty = item.quantity
    if qty and qty > 0 and unit_label:
        return f"({qty:g} {unit_label}) {query}"
    if unit_label:
        return f"({unit_label}) {query}"
    if qty and qty > 0:
        return f"[{qty:g}] {query}"
    return query


def group_services_to_prompt(group: BudgetItem) -> str:
    terms = [
        service_to_prompt_term(child)
        for child in group.children
        if child.row_type == ROW_TYPE_SERVICO
    ]
    return "\n".join(terms)


def clear_group_services(group: BudgetItem) -> int:
    before = len(group.children)
    group.children = [c for c in group.children if c.row_type != ROW_TYPE_SERVICO]
    return before - len(group.children)


def _make_memory_row(service: BudgetItem, note: str) -> BudgetItem:
    return BudgetItem(
        row_id=uuid.uuid4().hex[:12],
        code=f"{service.code}.m1",
        name=note,
        level=service.level + 1,
        quantity=0,
        unit="",
        unit_cost=0,
        unit_price=0,
        total_price=0,
        row_type="MEMORIA",
        item_type=BudgetItemType.INPUT,
        parent_code=service.code,
        calculation_note=note,
        metadata={"is_memory_row": True},
    )


def service_from_price_item(
    price: PriceItem,
    *,
    container: BudgetItem,
    code: str,
    bdi_calc: BdiCalculator,
    quantity: float = 1.0,
    pricing_query: str = "",
    unit_hint: str | None = None,
) -> BudgetItem:
    price_sem = float((price.metadata or {}).get("price_sem_desoneracao") or price.price)
    unit = unit_hint or price.unit or ""
    item = BudgetItem(
        row_id=uuid.uuid4().hex[:12],
        code=code,
        name=price.description,
        level=container.level + 1,
        quantity=quantity,
        unit=unit,
        unit_cost=price.price,
        unit_cost_semd=price_sem,
        unit_price=0,
        unit_price_semd=0,
        total_price=0,
        total_price_semd=0,
        source_base=price.source.upper(),
        source_code=price.code,
        parent_code=container.code,
        row_type=ROW_TYPE_SERVICO,
        item_type=BudgetItemType.COMPOSITION,
        bdi_rate=container.bdi_rate,
        bdi_label=container.bdi_label,
        pricing_query=pricing_query or price.description,
        metadata={"editable": True, "manual": True},
    )
    bdi_calc.apply_to_item(item)
    item.recompute_total()
    note = f"quantidade = {quantity:g} {unit}".strip() if quantity else "quantidade = a definir"
    item.children = [_make_memory_row(item, note)]
    return item


def add_etapa(
    roots: list[BudgetItem],
    name: str,
    project: BudgetProjectMetadata,
) -> BudgetItem:
    code = _next_etapa_code(roots)
    etapa = BudgetItem(
        row_id=uuid.uuid4().hex[:12],
        code=code,
        name=normalize_group_name(name),
        level=0,
        quantity=0,
        unit="",
        unit_cost=0,
        unit_price=0,
        total_price=0,
        row_type=ROW_TYPE_ETAPA,
        item_type=BudgetItemType.GROUP,
        bdi_rate=project.bdi.rate_com_desoneracao,
        bdi_label=project.bdi.label,
        metadata={"manual": True},
    )
    roots.append(etapa)
    return etapa


def add_subetapa(
    roots: list[BudgetItem],
    parent_code: str,
    name: str,
    project: BudgetProjectMetadata,
) -> BudgetItem:
    parent = find_group(roots, parent_code)
    if not parent:
        raise ValueError(f"Grupo pai não encontrado: {parent_code}")
    code = _next_subetapa_code(parent)
    sub = BudgetItem(
        row_id=uuid.uuid4().hex[:12],
        code=code,
        name=normalize_group_name(name),
        level=parent.level + 1,
        quantity=0,
        unit="",
        unit_cost=0,
        unit_price=0,
        total_price=0,
        row_type=ROW_TYPE_SUB_ETAPA,
        item_type=BudgetItemType.GROUP,
        parent_code=parent.code,
        bdi_rate=project.bdi.rate_com_desoneracao,
        bdi_label=project.bdi.label,
        metadata={"manual": True},
    )
    parent.children.append(sub)
    parent.recompute_total()
    return sub


def update_group_name(group: BudgetItem, name: str) -> None:
    group.name = normalize_group_name(name)


def delete_item(roots: list[BudgetItem], row_id: str) -> bool:
    item, parent, siblings = find_item(roots, row_id=row_id)
    if not item:
        return False
    siblings.remove(item)
    if parent:
        parent.recompute_total()
    else:
        for root in roots:
            root.recompute_total()
    return True


def update_service_quantity(
    svc: BudgetItem,
    quantity: float,
    bdi_calc: BdiCalculator,
) -> None:
    svc.quantity = quantity
    if svc.unit_cost > 0:
        svc.unit_price = bdi_calc.config.price_with_bdi(svc.unit_cost, True)
        svc.unit_price_semd = bdi_calc.config.price_with_bdi(
            svc.unit_cost_semd or svc.unit_cost, False
        )
    svc._sync_effective_leaf()
    svc.recompute_total()
    note = f"quantidade = {quantity:g} {svc.unit}".strip() if quantity else "quantidade = a definir"
    for child in svc.children:
        if child.metadata.get("is_memory_row"):
            child.name = note
            child.calculation_note = note
            break


def apply_quantity_to_group(
    group: BudgetItem,
    quantity: float,
    project: BudgetProjectMetadata,
    *,
    include_subgroups: bool = True,
) -> int:
    bdi_calc = BdiCalculator(project.bdi)
    count = 0

    def walk(node: BudgetItem) -> None:
        nonlocal count
        for child in node.children:
            if child.row_type == ROW_TYPE_SERVICO:
                update_service_quantity(child, quantity, bdi_calc)
                count += 1
            elif child.row_type == ROW_TYPE_SUB_ETAPA and include_subgroups:
                walk(child)

    walk(group)
    group.recompute_total()
    return count


def compose_group_from_prompt(
    container: BudgetItem,
    prompt: str,
    engine: PricingEngine,
    project: BudgetProjectMetadata,
    source_priority: list[str] | None = None,
    default_quantity: float | None = None,
) -> tuple[list[BudgetItem], list[dict[str, Any]]]:
    bdi_calc = BdiCalculator(project.bdi)
    added: list[BudgetItem] = []
    log: list[dict[str, Any]] = []
    priority = source_priority or ["sinapi"]

    for raw_term in split_composition_prompt(prompt):
        query, unit_hint, term_qty = parse_term_hints(raw_term)
        if len(query) < 2:
            continue
        resolved_qty = term_qty if term_qty is not None else default_quantity
        if resolved_qty is None:
            resolved_qty = 0.0
        request = build_price_request(
            query,
            unit=unit_hint,
            source_priority=priority,
            limit=8,
        )
        results = engine.resolve_many(request, best_only=False)
        if not results:
            log.append(
                {
                    "term": raw_term,
                    "query": query,
                    "unit_hint": unit_hint,
                    "resolved": False,
                    "reason": "sem match",
                }
            )
            continue

        price = results[0]
        if unit_hint and price.unit and price.unit.upper() != unit_hint:
            for candidate in results:
                if candidate.unit and candidate.unit.upper() == unit_hint:
                    price = candidate
                    break

        code = _next_service_code(container)
        svc = service_from_price_item(
            price,
            container=container,
            code=code,
            bdi_calc=bdi_calc,
            quantity=resolved_qty,
            pricing_query=query,
            unit_hint=unit_hint,
        )
        container.children.append(svc)
        added.append(svc)
        log.append(
            {
                "term": raw_term,
                "query": query,
                "unit_hint": unit_hint,
                "quantity": resolved_qty,
                "quantity_source": "term" if term_qty is not None else ("default" if default_quantity is not None else "none"),
                "resolved": True,
                "code": price.code,
                "description": price.description[:120],
                "unit": svc.unit,
                "price": price.price,
            }
        )

    container.recompute_total()
    return added, log


def recompose_group_from_prompt(
    container: BudgetItem,
    prompt: str,
    engine: PricingEngine,
    project: BudgetProjectMetadata,
    source_priority: list[str] | None = None,
    default_quantity: float | None = None,
) -> tuple[list[BudgetItem], list[dict[str, Any]], int]:
    removed = clear_group_services(container)
    added, log = compose_group_from_prompt(
        container,
        prompt,
        engine,
        project,
        source_priority=source_priority,
        default_quantity=default_quantity,
    )
    return added, log, removed


def replace_service_from_price(
    roots: list[BudgetItem],
    row_id: str,
    price: PriceItem,
    project: BudgetProjectMetadata,
    *,
    unit_hint: str | None = None,
    pricing_query: str = "",
) -> BudgetItem:
    item, parent, _ = find_item(roots, row_id=row_id)
    if not item or item.row_type != ROW_TYPE_SERVICO:
        raise ValueError(f"Serviço não encontrado: {row_id}")

    qty = item.quantity
    bdi_calc = BdiCalculator(project.bdi)
    price_sem = float((price.metadata or {}).get("price_sem_desoneracao") or price.price)
    item.name = price.description
    item.unit = unit_hint or price.unit or item.unit
    item.unit_cost = price.price
    item.unit_cost_semd = price_sem
    item.source_base = price.source.upper()
    item.source_code = price.code
    item.pricing_query = pricing_query or price.description
    if item.unit_cost > 0:
        item.unit_price = bdi_calc.config.price_with_bdi(item.unit_cost, True)
        item.unit_price_semd = bdi_calc.config.price_with_bdi(item.unit_cost_semd, False)
    item._sync_effective_leaf()
    item.recompute_total()
    note = f"quantidade = {qty:g} {item.unit}".strip() if qty else "quantidade = a definir"
    for child in item.children:
        if child.metadata.get("is_memory_row"):
            child.name = note
            child.calculation_note = note
            break
    if parent:
        parent.recompute_total()
    for root in roots:
        root.recompute_total()
    return item


compose_etapa_from_prompt = compose_group_from_prompt


def add_service_to_group(
    container: BudgetItem,
    price: PriceItem,
    project: BudgetProjectMetadata,
    quantity: float = 1.0,
    unit_hint: str | None = None,
) -> BudgetItem:
    bdi_calc = BdiCalculator(project.bdi)
    code = _next_service_code(container)
    svc = service_from_price_item(
        price,
        container=container,
        code=code,
        bdi_calc=bdi_calc,
        quantity=quantity,
        unit_hint=unit_hint,
    )
    container.children.append(svc)
    container.recompute_total()
    return svc


add_service_to_etapa = add_service_to_group


def import_etapas_from_sidecar(
    roots: list[BudgetItem],
    etapas_data: list[dict[str, Any]],
    project: BudgetProjectMetadata,
    *,
    include_services: bool = False,
) -> int:
    count = 0
    for etapa_data in etapas_data:
        name = str(etapa_data.get("name") or "").strip()
        if not name:
            continue
        etapa = add_etapa(roots, name, project)
        count += 1
        if not include_services:
            continue
        for svc_data in etapa_data.get("services") or []:
            svc_name = str(svc_data.get("name") or "").strip()
            if not svc_name:
                continue
            from pricing.models.price_item import PriceItem as PI

            price = PI(
                code=str(svc_data.get("sinapi_code") or svc_data.get("code") or ""),
                description=svc_name,
                unit=str(svc_data.get("unit") or ""),
                price=0,
                source="sinapi",
            )
            add_service_to_group(etapa, price, project, quantity=0)
        etapa.recompute_total()
    return count


def refresh_calculation_memory(roots: list[BudgetItem]) -> list[dict[str, Any]]:
    calc = BudgetCalculator()
    memory: list[dict[str, Any]] = []
    for root in roots:
        memory.extend(calc.build_calculation_memory(root))
    return memory
