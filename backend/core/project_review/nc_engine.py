"""Engine de não conformidades (Módulo H)."""

from __future__ import annotations

import uuid
from typing import Any

from core.project_review.constants import NCCriticidade, NCStatus


def nc_from_agent_payload(
    nc_data: dict[str, Any],
    *,
    project_id: uuid.UUID,
    review_id: uuid.UUID | None,
    index: int,
    project_file_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    codigo = nc_data.get("codigo") or f"NC-{index:03d}"
    return {
        "project_id": project_id,
        "review_id": review_id,
        "project_file_id": project_file_id,
        "codigo": codigo,
        "categoria": _normalize_category(nc_data.get("categoria")),
        "criticidade": _normalize_criticidade(nc_data.get("criticidade")),
        "descricao": nc_data.get("descricao") or "Não conformidade identificada",
        "evidencia": nc_data.get("evidencia"),
        "norma": nc_data.get("norma"),
        "impacto": nc_data.get("impacto"),
        "recomendacao": nc_data.get("recomendacao"),
        "status": NCStatus.ABERTA.value,
        "extra": nc_data.get("extra"),
    }


def merge_nc_lists(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for source in sources:
        for nc in source:
            key = (nc.get("codigo"), nc.get("descricao", "")[:80])
            if key in seen:
                continue
            seen.add(key)
            merged.append(nc)
    return merged


def compare_nc_versions(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compara NCs entre revisões V1 e V2 (Módulo O)."""
    prev_map = {nc["codigo"]: nc for nc in previous if nc.get("codigo")}
    curr_map = {nc["codigo"]: nc for nc in current if nc.get("codigo")}

    result = {
        "corrigido": [],
        "parcialmente_corrigido": [],
        "nao_corrigido": [],
        "nova_ocorrencia": [],
    }

    for code, nc in curr_map.items():
        if code not in prev_map:
            result["nova_ocorrencia"].append(nc)
        elif prev_map[code].get("status") != nc.get("status"):
            if nc.get("status") == NCStatus.CORRIGIDA.value:
                result["corrigido"].append(nc)
            else:
                result["parcialmente_corrigido"].append(nc)
        else:
            result["nao_corrigido"].append(nc)

    for code, nc in prev_map.items():
        if code not in curr_map and nc.get("status") != NCStatus.CORRIGIDA.value:
            result["corrigido"].append({**nc, "status": NCStatus.CORRIGIDA.value})

    return result


def _normalize_category(value: Any) -> str:
    if not value:
        return "documental"
    v = str(value).lower().replace(" ", "_")
    allowed = {
        "documental",
        "estrutural",
        "arquitetonica",
        "hidraulica",
        "eletrica",
        "pci",
        "orcamentaria",
    }
    return v if v in allowed else "documental"


def _normalize_criticidade(value: Any) -> str:
    if not value:
        return NCCriticidade.MEDIA.value
    v = str(value).lower().replace("é", "e")
    mapping = {"baixa": "baixa", "media": "media", "média": "media", "alta": "alta", "critica": "critica", "crítica": "critica"}
    return mapping.get(v, NCCriticidade.MEDIA.value)
