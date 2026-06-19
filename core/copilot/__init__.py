"""Copilot v1 — planejamento, execução multi-agente e avaliação de qualidade."""

from core.copilot.copilot_engine import run_copilot
from core.copilot.intent_analyzer import analyze_intent, IntentResult
from core.copilot.task_planner import build_plan, ExecutionPlan
from core.copilot.execution_graph import ExecutionGraph, ExecutionGraphResult
from core.copilot.response_synthesizer import synthesize_response
from core.copilot.quality_evaluator import evaluate_quality

__all__ = [
    "run_copilot",
    "analyze_intent",
    "IntentResult",
    "build_plan",
    "ExecutionPlan",
    "ExecutionGraph",
    "ExecutionGraphResult",
    "synthesize_response",
    "evaluate_quality",
]
