"""
Execution Graph — executa plano via dispatcher existente + ContextGraph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from core.agent_registry import get_agent_name
from core.context_graph import ContextGraph
from core.copilot.task_planner import ExecutionPlan, PlanStep
from core.dispatcher import dispatch

logger = logging.getLogger(__name__)


@dataclass
class StepExecutionResult:
    step: PlanStep
    response: dict[str, Any]
    success: bool
    error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step.step_id,
            "order": self.step.order,
            "discipline": self.step.discipline,
            "agent": self.step.agent,
            "description": self.step.description,
            "depends_on": self.step.depends_on,
            "success": self.success,
            "error": self.error,
            "response": self.response,
        }


@dataclass
class ExecutionGraphResult:
    step_results: list[StepExecutionResult] = field(default_factory=list)
    context_graph: ContextGraph = field(default_factory=ContextGraph)

    @property
    def completed_count(self) -> int:
        return sum(1 for r in self.step_results if r.success)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.step_results if r.error)


class ExecutionGraph:
    """
    Executa plano Copilot usando dispatcher + ContextGraph compartilhado.

    Não altera dispatcher — apenas monta route_result e consome respostas.
    """

    def __init__(
        self,
        *,
        use_rag: bool = True,
        persist: bool = False,
        conversation_id: Optional[str] = None,
    ):
        self.use_rag = use_rag
        self.persist = persist
        self.conversation_id = conversation_id
        self.context_graph = ContextGraph()

    def execute_plan(
        self,
        plan: ExecutionPlan,
        original_text: str,
    ) -> ExecutionGraphResult:
        result = ExecutionGraphResult(context_graph=self.context_graph)
        executed_disciplines: list[str] = []

        for step in plan.steps:
            step_result = self._execute_step(step, original_text, executed_disciplines)
            result.step_results.append(step_result)
            executed_disciplines.append(step.discipline)

        return result

    def _execute_step(
        self,
        step: PlanStep,
        original_text: str,
        prior_disciplines: list[str],
    ) -> StepExecutionResult:
        context = None
        if step.use_context and self.context_graph.nodes:
            context = self.context_graph.build_global_context()

        route_result = {
            "discipline": step.discipline,
            "input": original_text,
            "context": context,
            "agent": get_agent_name(step.discipline),
            "_use_rag": self.use_rag,
        }
        if self.conversation_id:
            route_result["_conversation_id"] = self.conversation_id

        try:
            response = dispatch(route_result, persist=self.persist)
            error = bool(response.get("error"))
            success = not error and bool(
                response.get("result") or response.get("response")
            )
        except Exception as exc:
            logger.warning(
                "Copilot step failed discipline=%s error=%s",
                step.discipline,
                exc,
            )
            response = {
                "discipline": step.discipline,
                "agent": step.agent,
                "input": original_text,
                "result": f"Falha na execução: {exc}",
                "error": True,
            }
            error = True
            success = False

        self.context_graph.add_result(
            discipline=step.discipline,
            data={
                "result": response.get("result") or response.get("response"),
                "agent": response.get("agent", step.agent),
                "input": original_text,
                "step_id": step.step_id,
                "error": error,
                "extra": response.get("extra"),
            },
            depends_on=step.depends_on or prior_disciplines,
        )

        return StepExecutionResult(
            step=step,
            response=response,
            success=success,
            error=error,
        )
