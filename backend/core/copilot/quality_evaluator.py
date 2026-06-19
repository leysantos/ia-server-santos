"""
Quality Evaluator — score de qualidade da resposta Copilot (0 a 1).

Rule-based — sem LLM, sem alterar agentes ou RAG.
"""

from __future__ import annotations

import re
from typing import Any

from core.copilot.execution_graph import ExecutionGraphResult
from core.copilot.task_planner import ExecutionPlan

NBR_PATTERN = re.compile(r"NBR\s*\d+", re.IGNORECASE)
MIN_USEFUL_LENGTH = 80


def evaluate_quality(
    synthesis: dict[str, Any],
    execution: ExecutionGraphResult,
    plan: ExecutionPlan,
) -> dict[str, Any]:
    """
    Avalia qualidade da resposta final (0.0 – 1.0).

    Fatores:
    - taxa de conclusão das etapas
    - cobertura de disciplinas planejadas
    - profundidade das respostas (comprimento)
    - citações normativas (NBR)
    - ausência de erros
    """
    total_steps = max(len(plan.steps), 1)
    completed = execution.completed_count
    errors = execution.error_count

    factors: dict[str, float] = {}

    # Conclusão (30%)
    completion_rate = completed / total_steps
    factors["completion_rate"] = round(completion_rate, 3)

    # Cobertura de disciplinas (20%)
    planned = set(plan.disciplines)
    executed_ok = {
        r.step.discipline for r in execution.step_results if r.success
    }
    coverage = len(executed_ok & planned) / max(len(planned), 1)
    factors["discipline_coverage"] = round(coverage, 3)

    # Profundidade de conteúdo (25%)
    contents = [
        (synthesis.get("by_discipline") or {}).get(d, {}).get("content", "")
        for d in plan.disciplines
    ]
    depth_scores = [
        1.0 if len(c) >= MIN_USEFUL_LENGTH else len(c) / MIN_USEFUL_LENGTH
        for c in contents
    ]
    depth = sum(depth_scores) / max(len(depth_scores), 1)
    factors["content_depth"] = round(depth, 3)

    # Citações normativas (15%)
    all_text = synthesis.get("final_report", "") + synthesis.get("technical_summary", "")
    nbr_count = len(NBR_PATTERN.findall(all_text))
    normative = min(1.0, nbr_count / max(len(plan.disciplines), 1))
    factors["normative_references"] = round(normative, 3)

    # Penalidade por erros (10%)
    error_penalty = 1.0 - (errors / total_steps)
    factors["error_resilience"] = round(max(0.0, error_penalty), 3)

    score = (
        0.30 * completion_rate
        + 0.20 * coverage
        + 0.25 * depth
        + 0.15 * normative
        + 0.10 * error_penalty
    )
    score = round(min(1.0, max(0.0, score)), 3)

    return {
        "score": score,
        "grade": _score_to_grade(score),
        "factors": factors,
        "completed_steps": completed,
        "total_steps": total_steps,
        "error_steps": errors,
        "recommendations": _recommendations(factors, errors),
    }


def _score_to_grade(score: float) -> str:
    if score >= 0.85:
        return "excelente"
    if score >= 0.70:
        return "bom"
    if score >= 0.50:
        return "aceitável"
    if score >= 0.30:
        return "insuficiente"
    return "crítico"


def _recommendations(factors: dict[str, float], errors: int) -> list[str]:
    recs: list[str] = []
    if factors.get("completion_rate", 0) < 1.0:
        recs.append("Reexecutar etapas que falharam ou simplificar a solicitação.")
    if factors.get("content_depth", 0) < 0.5:
        recs.append("Fornecer mais detalhes no input (dimensões, materiais, normas aplicáveis).")
    if factors.get("normative_references", 0) < 0.5:
        recs.append("Solicitar citação explícita de NBRs relevantes por disciplina.")
    if errors > 0:
        recs.append("Verificar disponibilidade do Ollama e tentar novamente.")
    if not recs:
        recs.append("Resposta adequada para revisão técnica preliminar.")
    return recs
