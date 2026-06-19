"""
Execution Evaluator — avalia completude e sucesso da execução multi-agente.
"""

from __future__ import annotations

from typing import Any

from core.evaluation_v2.quality_metrics import StageScore, clamp_score


def evaluate_execution(copilot_output: dict[str, Any]) -> StageScore:
    """Avalia taxa de conclusão, erros e cobertura das etapas executadas."""
    execution = copilot_output.get("execution") or []
    plan = copilot_output.get("plan") or []
    result = copilot_output.get("result") or {}
    issues: list[str] = []
    factors: dict[str, float] = {}

    total_planned = max(len(plan), 1)
    total_executed = len(execution)

    if total_executed == 0:
        return StageScore(
            name="execution_completeness",
            score=0.0,
            issues=["nenhuma etapa executada"],
        )

    # Taxa execução vs plano
    execution_coverage = min(1.0, total_executed / total_planned)
    factors["execution_coverage"] = round(execution_coverage, 3)
    if total_executed < total_planned:
        issues.append(
            f"execução incompleta: {total_executed}/{total_planned} etapas"
        )

    # Sucesso por etapa
    successes = sum(1 for step in execution if step.get("success"))
    success_rate = successes / max(total_executed, 1)
    factors["success_rate"] = round(success_rate, 3)
    if success_rate < 1.0:
        failed = [s.get("discipline") for s in execution if not s.get("success")]
        issues.append(f"etapas com falha: {', '.join(failed)}")

    # Erros explícitos
    errors = sum(1 for step in execution if step.get("error"))
    error_rate = errors / max(total_executed, 1)
    error_resilience = 1.0 - error_rate
    factors["error_resilience"] = round(error_resilience, 3)
    if errors > 0:
        issues.append(f"{errors} etapa(s) com flag error=true")

    # Alinhamento result.completed_steps
    completed_reported = result.get("completed_steps", successes)
    completed_ratio = completed_reported / total_planned
    factors["completed_ratio"] = round(completed_ratio, 3)

    # ContextGraph populado
    context_graph = copilot_output.get("context_graph") or {}
    nodes = context_graph.get("nodes") or {}
    context_score = min(1.0, len(nodes) / total_planned)
    factors["context_graph_coverage"] = round(context_score, 3)

    score = clamp_score(
        0.35 * success_rate
        + 0.25 * execution_coverage
        + 0.20 * error_resilience
        + 0.20 * context_score
    )

    return StageScore(
        name="execution_completeness",
        score=score,
        issues=issues,
        factors=factors,
    )
