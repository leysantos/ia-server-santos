"""Proteções de concorrência — revisão técnica vs análise visual."""

from __future__ import annotations

from fastapi import HTTPException

from core.runtime.job_registry import get_job_registry


def assert_review_can_start(project_id: str) -> None:
    """
    Impede revisão técnica enquanto análise visual do mesmo projeto está ativa.
    Evita dupla carga Gemma/Qwen na GPU (OOM e queda da API).
    """
    registry = get_job_registry()
    for job in registry.list_jobs(active_only=True, limit=20):
        if job.get("kind") != "vision":
            continue
        if job.get("project_id") and str(job.get("project_id")) != str(project_id):
            continue
        label = job.get("label") or "Análise visual"
        raise HTTPException(
            status_code=409,
            detail=(
                f"{label} ainda em andamento neste projeto. "
                "Aguarde a conclusão, cancele no Console (/console) ou use revisão "
                "sem reprocessar visão (enable_vision=false)."
            ),
        )
