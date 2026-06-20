"""Motor de scoring de conformidade (Módulo L)."""

from __future__ import annotations

from typing import Any

from core.project_review.constants import NCCriticidade


def compute_scores(
    *,
    analysis: dict[str, Any],
    nonconformities: list[dict[str, Any]],
    compat_report: dict[str, Any] | None = None,
    budget_report: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Calcula indicadores 0-100 por dimensão."""
    base_penalty = _nc_penalty(nonconformities)

    structural_nc = [n for n in nonconformities if n.get("categoria") == "estrutural"]
    pci_nc = [n for n in nonconformities if n.get("categoria") == "pci"]
    doc_nc = [n for n in nonconformities if n.get("categoria") == "documental"]
    budget_nc = [n for n in nonconformities if n.get("categoria") == "orcamentaria"]

    conflicts = len(analysis.get("conflitos") or [])
    conflicts += len((compat_report or {}).get("interferencias") or [])

    budget_score = 100.0 - _nc_penalty(budget_nc)
    if budget_report:
        budget_score -= len(budget_report.get("itens_faltantes") or []) * 3
        budget_score -= len(budget_report.get("quantitativos_incompativeis") or []) * 5
        budget_score = max(0.0, min(100.0, budget_score))

    scores = {
        "conformidade_geral": max(0.0, min(100.0, 100.0 - base_penalty - conflicts * 4)),
        "conformidade_estrutural": max(0.0, min(100.0, 100.0 - _nc_penalty(structural_nc))),
        "conformidade_pci": max(0.0, min(100.0, 100.0 - _nc_penalty(pci_nc))),
        "conformidade_documental": max(0.0, min(100.0, 100.0 - _nc_penalty(doc_nc))),
        "conformidade_orcamentaria": budget_score,
    }
    return {k: round(v, 1) for k, v in scores.items()}


def _nc_penalty(ncs: list[dict[str, Any]]) -> float:
    weights = {
        NCCriticidade.BAIXA.value: 2,
        NCCriticidade.MEDIA.value: 5,
        NCCriticidade.ALTA.value: 10,
        NCCriticidade.CRITICA.value: 20,
    }
    total = 0.0
    for nc in ncs:
        total += weights.get(str(nc.get("criticidade", "media")).lower(), 5)
    return min(80.0, total)
