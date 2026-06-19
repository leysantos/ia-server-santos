"""
Copilot Engine — pipeline principal do Copilot v1.

input → intent → plan → execute → synthesize → evaluate
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from core.copilot.execution_graph import ExecutionGraph
from core.copilot.intent_analyzer import analyze_intent
from core.copilot.quality_evaluator import evaluate_quality
from core.copilot.response_synthesizer import synthesize_response
from core.copilot.task_planner import build_plan

logger = logging.getLogger(__name__)


def run_copilot(
    text: str,
    *,
    use_rag: bool = True,
    persist: bool = False,
    conversation_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Executa pipeline completo do Copilot de engenharia civil.

    Não altera Router, Dispatcher, RAG v2 nem Orchestrator — camada nova acima.
    """
    text = text.strip()
    if not text:
        raise ValueError("text não pode ser vazio")

    conv_id = conversation_id or str(uuid.uuid4())

    # 1. Intent
    intent_result = analyze_intent(text)
    logger.info(
        "copilot intent=%s confidence=%.2f disciplines_hint=%s",
        intent_result.intent,
        intent_result.confidence,
        intent_result.disciplines_hint,
    )

    # 2. Plan
    plan = build_plan(text, intent_result)

    # 3. Execute
    executor = ExecutionGraph(
        use_rag=use_rag,
        persist=persist,
        conversation_id=conv_id,
    )
    execution = executor.execute_plan(plan, text)

    # 4. Synthesize
    synthesis = synthesize_response(plan, execution)

    # 5. Evaluate
    evaluation = evaluate_quality(synthesis, execution, plan)

    return {
        "input": text,
        "conversation_id": conv_id,
        "intent": intent_result.intent,
        "intent_confidence": intent_result.confidence,
        "matched_categories": intent_result.matched_categories,
        "plan": plan.to_dict(),
        "disciplines": plan.disciplines,
        "result": synthesis,
        "evaluation": evaluation,
        "context_graph": executor.context_graph.to_dict(),
        "execution": [r.to_dict() for r in execution.step_results],
    }
