"""Facade de orçamento — delega roteamento ao ModelRouter central."""

from __future__ import annotations

from typing import Any, Literal

from config import settings
from core.models.model_router import (
    estimate_budget_complexity,
    estimate_pricing_complexity,
    get_model_router,
    routed_generate,
)

BudgetTask = Literal["wbs", "pricing"]

# Re-export para compatibilidade
__all__ = [
    "BudgetTask",
    "budget_generate",
    "budget_routing_enabled",
    "estimate_budget_complexity",
    "estimate_pricing_complexity",
    "resolve_budget_task_type",
]


def resolve_budget_task_type(task: BudgetTask, complexity: str) -> str:
    return get_model_router().resolve_budget_task_type(task, complexity)


def budget_routing_enabled() -> bool:
    return (
        settings.USE_MODEL_ROUTER
        or settings.USE_MODEL_EVALUATION
        or settings.USE_BUDGET_SMART_ROUTING
    )


def budget_generate(
    prompt: str,
    *,
    user_text: str,
    task: BudgetTask,
    format_json: bool = False,
    complexity: str | None = None,
    client: Any = None,
    discipline: str = "ORÇAMENTO",
    line_name: str | None = None,
    query: str | None = None,
    service_context: str | None = None,
    intent: dict[str, Any] | None = None,
    timeout: int | None = None,
) -> tuple[str, str]:
    from models.ollama_client import OllamaClient

    router = get_model_router()
    if task == "wbs":
        cx = complexity or estimate_budget_complexity(user_text, intent)
    else:
        cx = complexity or estimate_pricing_complexity(line_name, query, service_context)

    read_timeout = timeout or settings.OLLAMA_BUDGET_TIMEOUT
    llm = client or OllamaClient(timeout=read_timeout)

    if not budget_routing_enabled():
        return llm.generate(prompt, format_json=format_json)

    task_type = router.resolve_budget_task_type(task, cx)
    ctx = {
        "text": user_text,
        "input": user_text,
        "complexity": cx,
        "discipline": discipline,
        "module": "budget",
        "budget_task": task,
        "intent": intent,
    }
    return routed_generate(
        prompt,
        task_type,
        context=ctx,
        module="budget",
        discipline=discipline,
        client=llm,
        timeout=read_timeout,
        format_json=format_json,
    )
