"""
Evaluation Engine — pipeline principal do Evaluation Loop v2.

evaluate(copilot_output) → scores por etapa + final_score + issues
"""

from __future__ import annotations

from typing import Any

from core.evaluation_v2.execution_evaluator import evaluate_execution
from core.evaluation_v2.intent_evaluator import evaluate_intent
from core.evaluation_v2.plan_evaluator import evaluate_plan
from core.evaluation_v2.quality_metrics import (
    collect_issues,
    grade_from_score,
    weighted_final_score,
)
from core.evaluation_v2.response_evaluator import evaluate_response


def evaluate(copilot_output: dict[str, Any]) -> dict[str, Any]:
    """
    Avalia saída completa do Copilot v1 em quatro níveis + score final.

    Não altera copilot_output — retorna dict de avaliação independente.
    """
    stages = [
        evaluate_intent(copilot_output),
        evaluate_plan(copilot_output),
        evaluate_execution(copilot_output),
        evaluate_response(copilot_output),
    ]

    scores = {stage.name: stage.score for stage in stages}
    final_score = weighted_final_score(scores)
    issues = collect_issues(stages)

    return {
        "intent_accuracy": scores["intent_accuracy"],
        "plan_quality": scores["plan_quality"],
        "execution_completeness": scores["execution_completeness"],
        "response_quality": scores["response_quality"],
        "final_score": final_score,
        "grade": grade_from_score(final_score),
        "issues": issues,
        "stages": [s.to_dict() for s in stages],
        "input": copilot_output.get("input"),
        "intent": copilot_output.get("intent"),
        "conversation_id": copilot_output.get("conversation_id"),
    }
