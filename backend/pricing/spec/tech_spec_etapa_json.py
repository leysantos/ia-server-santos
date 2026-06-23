"""JSON estruturado por etapa WBS para geração de especificação técnica."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterator

from pricing.budget.budget_session import BudgetSession
from pricing.budget.ppd_layout import ROW_TYPE_SUB_ETAPA
from pricing.models.budget_item import BudgetItem
from pricing.spec.tech_spec_wbs import (
    _collect_services_under,
    _is_memory_item,
    iter_etapas,
    iter_ordered_services,
)


@dataclass
class EtapaGenerationChunk:
    etapa_code: str
    etapa_name: str
    label: str
    json_text: str
    payload: dict[str, Any]
    service_codes: list[str] = field(default_factory=list)
    part_index: int = 1
    part_total: int = 1


def _service_to_dict(svc: BudgetItem) -> dict[str, Any]:
    mem = svc.calculation_note or ""
    for child in svc.children:
        if _is_memory_item(child) and (child.calculation_note or child.name):
            mem = child.calculation_note or child.name or mem
    row: dict[str, Any] = {
        "codigo_wbs": svc.code,
        "descricao": svc.name,
        "quantidade": svc.quantity,
        "unidade": svc.unit or "",
        "preco_unitario_comd": float(svc.unit_price or 0),
        "total_comd": float(svc.total_price or 0),
    }
    if svc.source_code:
        row["base_preco"] = (svc.source_base or "SINAPI").strip()
        row["codigo_composicao"] = str(svc.source_code)
    if mem:
        row["memoria_calculo"] = mem[:500]
    return row


def build_etapa_json_payload(session: BudgetSession, etapa: BudgetItem) -> dict[str, Any]:
    """Monta payload JSON com todos os serviços da etapa na ordem do orçamento."""
    proj = session.project
    grupos: list[dict[str, Any]] = []
    service_codes: list[str] = []

    subetapas = [
        c for c in etapa.children if c.row_type == ROW_TYPE_SUB_ETAPA and not _is_memory_item(c)
    ]
    if subetapas:
        for sub in subetapas:
            servicos = [_service_to_dict(s) for s in _collect_services_under(sub)]
            if not servicos:
                continue
            service_codes.extend(s["codigo_wbs"] for s in servicos)
            grupos.append(
                {
                    "tipo": "sub_etapa",
                    "codigo": sub.code,
                    "nome": sub.name,
                    "servicos": servicos,
                }
            )
    else:
        for svc in _collect_services_under(etapa):
            service_codes.append(svc.code)
            grupos.append(
                {
                    "tipo": "servico",
                    "codigo": svc.code,
                    "nome": svc.name,
                    "servicos": [_service_to_dict(svc)],
                }
            )

    bases: list[dict[str, str]] = []
    for base in proj.price_bases or []:
        if not base.get("enabled", True):
            continue
        bases.append(
            {
                "fonte": str(base.get("label") or base.get("source", "")).upper(),
                "uf": str(base.get("uf") or ""),
                "referencia": str(base.get("reference") or ""),
            }
        )

    return {
        "etapa": {"codigo": etapa.code, "nome": etapa.name},
        "obra": {
            "projeto": proj.projeto or session.title,
            "objeto": proj.objeto or "",
            "local": proj.local or "",
            "orcamento": proj.orcamento or "",
        },
        "bases_precos": bases or [{"fonte": proj.base_preco or "Conforme orçamento"}],
        "grupos_wbs": grupos,
        "servicos_obrigatorios": service_codes,
        "total_servicos": len(service_codes),
    }


def iter_etapa_chunks(session: BudgetSession) -> Iterator[EtapaGenerationChunk]:
    """Um chunk por etapa do orçamento."""
    etapas = iter_etapas(session.roots)
    total = len(etapas)
    for idx, etapa in enumerate(etapas, start=1):
        payload = build_etapa_json_payload(session, etapa)
        if not payload["servicos_obrigatorios"]:
            continue
        yield EtapaGenerationChunk(
            etapa_code=etapa.code,
            etapa_name=etapa.name,
            label=f"etapa {etapa.code} — {etapa.name}",
            json_text=json.dumps(payload, ensure_ascii=False, indent=2),
            payload=payload,
            service_codes=list(payload["servicos_obrigatorios"]),
            part_index=idx,
            part_total=total,
        )


def services_for_etapa(roots: list[BudgetItem], etapa_code: str) -> list[BudgetItem]:
    return [svc for etapa, _sub, svc in iter_ordered_services(roots) if etapa.code == etapa_code]
