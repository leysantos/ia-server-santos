"""
Plan Evaluator — avalia qualidade do plano de execução do Copilot.
"""

from __future__ import annotations

from typing import Any

from core.evaluation_v2.quality_metrics import StageScore, clamp_score

INTENT_MIN_STEPS = {
    "structural": 1,
    "hydraulic": 1,
    "electrical": 1,
    "cost": 1,
    "general": 1,
    "multi_discipline": 3,
}


def evaluate_plan(copilot_output: dict[str, Any]) -> StageScore:
    """Avalia estrutura, cobertura e coerência do plano gerado."""
    plan = copilot_output.get("plan") or []
    intent = copilot_output.get("intent", "general")
    disciplines = copilot_output.get("disciplines") or []
    issues: list[str] = []
    factors: dict[str, float] = {}

    if not plan:
        return StageScore(
            name="plan_quality",
            score=0.0,
            issues=["plano vazio"],
        )

    # Quantidade de etapas adequada ao intent
    min_steps = INTENT_MIN_STEPS.get(intent, 1)
    step_count_score = min(1.0, len(plan) / min_steps)
    factors["step_count"] = round(step_count_score, 3)
    if len(plan) < min_steps:
        issues.append(
            f"plano insuficiente para intent {intent}: {len(plan)} < {min_steps} etapas"
        )

    # Ordem sequencial correta
    orders = [step.get("order", 0) for step in plan]
    order_ok = orders == list(range(1, len(plan) + 1))
    factors["sequential_order"] = 1.0 if order_ok else 0.5
    if not order_ok:
        issues.append("ordem das etapas inconsistente")

    # Disciplinas únicas e alinhadas
    plan_disciplines = [s.get("discipline") for s in plan if s.get("discipline")]
    unique_ratio = len(set(plan_disciplines)) / max(len(plan_disciplines), 1)
    factors["discipline_uniqueness"] = round(unique_ratio, 3)

    discipline_alignment = (
        len(set(plan_disciplines) & set(disciplines)) / max(len(disciplines), 1)
    )
    factors["discipline_alignment"] = round(discipline_alignment, 3)
    if discipline_alignment < 1.0:
        issues.append("disciplinas do plano divergem da lista consolidada")

    # Agentes definidos
    agents_defined = sum(1 for s in plan if s.get("agent")) / len(plan)
    factors["agents_defined"] = round(agents_defined, 3)
    if agents_defined < 1.0:
        issues.append("etapas sem agente associado")

    # Dependências em etapas posteriores
    deps_ok = True
    for i, step in enumerate(plan):
        if i == 0 and step.get("depends_on"):
            deps_ok = False
        if i > 0 and not step.get("use_context") and len(plan) > 1:
            pass  # use_context opcional
    factors["dependency_structure"] = 1.0 if deps_ok else 0.7
    if not deps_ok:
        issues.append("dependências inconsistentes na primeira etapa")

    score = clamp_score(
        0.30 * step_count_score
        + 0.20 * factors["sequential_order"]
        + 0.20 * discipline_alignment
        + 0.15 * agents_defined
        + 0.15 * unique_ratio
    )

    return StageScore(
        name="plan_quality",
        score=score,
        issues=issues,
        factors=factors,
    )
