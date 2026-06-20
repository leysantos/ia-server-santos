"""Compatibilização entre disciplinas (Módulo I)."""

from __future__ import annotations

from typing import Any


_DISCIPLINE_PAIRS = (
    ("arquitetura", "estrutura"),
    ("arquitetura", "eletrica"),
    ("arquitetura", "hidraulica"),
    ("estrutura", "pci"),
    ("estrutura", "orcamento"),
)


def analyze_compatibility(twin_payload: dict[str, Any]) -> dict[str, Any]:
    """Detecta conflitos e interferências entre disciplinas."""
    payload = twin_payload.get("payload") or twin_payload
    interferencias: list[dict[str, Any]] = []

    for disc_a, disc_b in _DISCIPLINE_PAIRS:
        block_a = payload.get(disc_a) or {}
        block_b = payload.get(disc_b) or {}
        elems_a = set(_element_types(block_a))
        elems_b = set(_element_types(block_b))

        if not block_a.get("documentos") and block_b.get("documentos"):
            interferencias.append(
                {
                    "tipo": "documento_ausente",
                    "disciplinas": [disc_a, disc_b],
                    "descricao": f"Disciplina {disc_a} sem documentos enquanto {disc_b} possui entregáveis",
                    "criticidade": "alta",
                }
            )

        if disc_a == "estrutura" and disc_b == "pci" and elems_a and not elems_b:
            interferencias.append(
                {
                    "tipo": "pci_incompleto",
                    "disciplinas": [disc_a, disc_b],
                    "descricao": "Projeto estrutural presente sem elementos PCI correspondentes",
                    "criticidade": "media",
                }
            )

        overlap = elems_a & elems_b
        if overlap and disc_a != disc_b:
            interferencias.append(
                {
                    "tipo": "elemento_compartilhado",
                    "disciplinas": [disc_a, disc_b],
                    "descricao": f"Elementos em comum requerem compatibilização: {sorted(overlap)[:5]}",
                    "criticidade": "baixa",
                }
            )

    return {
        "pares_analisados": list(_DISCIPLINE_PAIRS),
        "interferencias": interferencias,
        "total": len(interferencias),
    }


def _element_types(block: dict[str, Any]) -> list[str]:
    elements = block.get("elementos") or []
    types: list[str] = []
    for el in elements:
        if isinstance(el, dict):
            types.append(str(el.get("tipo") or el.get("type") or ""))
        else:
            types.append(str(el))
    return [t for t in types if t]
