"""Geração de memórias de cálculo (MCQ) — regras + IA opcional."""

from __future__ import annotations

import json
import re
from typing import Any

from pricing.budget.ppd_layout import ROW_TYPE_SERVICO, ROW_TYPE_SUB_ETAPA
from pricing.models.budget_item import BudgetItem


def _walk_services(node: BudgetItem) -> list[BudgetItem]:
    found: list[BudgetItem] = []
    if node.row_type == ROW_TYPE_SERVICO:
        found.append(node)
    for child in node.children:
        if child.row_type in (ROW_TYPE_SUB_ETAPA, "ETAPA"):
            found.extend(_walk_services(child))
        elif child.row_type == ROW_TYPE_SERVICO:
            found.append(child)
        elif child.metadata.get("is_memory_row"):
            continue
        else:
            found.extend(_walk_services(child))
    return found


def _rule_memory(service: BudgetItem) -> str:
    name = service.name.lower()
    unit = (service.unit or "").upper()
    qty = service.quantity or 0

    if qty > 0:
        base = f"quantidade = {qty:g} {unit}".strip()
    else:
        base = "quantidade = a definir"

    if unit in ("MES", "MÊS", "MÊS"):
        if any(k in name for k in ("engenheiro", "encarregado", "vigia", "auxiliar", "tecnico", "técnico")):
            return f"{base} · prazo de execução da obra (meses)"
    if unit == "H":
        return f"{base} · horas homem estimadas"
    if unit in ("M2", "M²"):
        if "area" in name or "área" in name or "superfície" in name:
            return f"{base} · área = comprimento × largura"
        return f"{base} · área (m²)"
    if unit in ("M3", "M³", "M3XKM"):
        return f"{base} · volume transportado / escavado"
    if unit == "M":
        return f"{base} · comprimento linear"
    if unit == "UN":
        return f"{base} · unidade(s)"
    if unit == "KG":
        return f"{base} · massa (kg)"
    if unit == "TXKM" or "KM" in unit:
        return f"{base} · tonelada × distância (DMT)"

    return base


def _apply_memory_to_service(service: BudgetItem, note: str) -> None:
    mem_children = [c for c in service.children if c.metadata.get("is_memory_row")]
    if mem_children:
        mem = mem_children[0]
        mem.name = note
        mem.calculation_note = note
    else:
        from pricing.budget.budget_structure import _make_memory_row

        service.children.append(_make_memory_row(service, note))


def generate_memories_for_group(
    group: BudgetItem,
    *,
    use_llm: bool = False,
    llm_client: Any = None,
    obra_context: str = "",
) -> list[dict[str, Any]]:
    """Gera memórias para todos os serviços sob etapa/sub-etapa."""
    services = _walk_services(group)
    log: list[dict[str, Any]] = []

    if use_llm and llm_client and services:
        llm_notes = _llm_generate_memories(services, group.name, obra_context, llm_client)
        for svc, note in zip(services, llm_notes):
            if note:
                _apply_memory_to_service(svc, note)
                log.append({"code": svc.code, "method": "llm", "note": note[:200]})
        return log

    for svc in services:
        note = _rule_memory(svc)
        _apply_memory_to_service(svc, note)
        log.append({"code": svc.code, "method": "rule", "note": note})
    return log


def generate_memories_for_session(
    roots: list[BudgetItem],
    *,
    group_code: str | None = None,
    use_llm: bool = False,
    llm_client: Any = None,
    obra_context: str = "",
) -> list[dict[str, Any]]:
    from pricing.budget.budget_structure import find_group

    log: list[dict[str, Any]] = []
    if group_code:
        group = find_group(roots, group_code)
        if not group:
            raise ValueError(f"Grupo não encontrado: {group_code}")
        log.extend(
            generate_memories_for_group(
                group,
                use_llm=use_llm,
                llm_client=llm_client,
                obra_context=obra_context,
            )
        )
        return log

    for root in roots:
        log.extend(
            generate_memories_for_group(
                root,
                use_llm=use_llm,
                llm_client=llm_client,
                obra_context=obra_context,
            )
        )
    return log


def _llm_generate_memories(
    services: list[BudgetItem],
    group_name: str,
    obra_context: str,
    llm_client: Any,
) -> list[str]:
    lines = [
        f"- {s.code} {s.name} ({s.unit or '?'}) qtd={s.quantity or '?'}"
        for s in services
    ]
    prompt = f"""Gere memória de cálculo PPD (MCQ) para cada serviço abaixo.
Obra: {obra_context or group_name}
Etapa: {group_name}

Serviços:
{chr(10).join(lines)}

Responda APENAS JSON array de strings, uma memória por serviço, na mesma ordem.
Exemplo: ["quantidade = 12 MES · prazo obra", "área = 20m × 2,5m = 50 M2"]
"""
    try:
        from core.models.budget_model_routing import budget_generate

        raw, _model = budget_generate(
            prompt,
            user_text=obra_context or group_name,
            task="wbs",
            client=llm_client,
        )
        text = raw.strip()
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        if isinstance(parsed, list) and len(parsed) == len(services):
            return [str(x) for x in parsed]
    except Exception:
        pass
    return [_rule_memory(s) for s in services]
