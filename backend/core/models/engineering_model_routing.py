"""Facade de engenharia no chat — delega roteamento ao ModelRouter central."""

from __future__ import annotations

from typing import Any

from config import settings
from core.models.model_router import (
    estimate_engineering_complexity,
    get_model_router,
    routed_generate,
)

__all__ = [
    "engineering_generate",
    "engineering_routing_enabled",
    "engineering_stream_models",
    "estimate_engineering_complexity",
    "resolve_engineering_task_type",
]


def resolve_engineering_task_type(complexity: str) -> str:
    return get_model_router().resolve_engineering_task_type(complexity)


def engineering_routing_enabled() -> bool:
    return (
        settings.USE_MODEL_ROUTER
        or settings.USE_MODEL_EVALUATION
        or settings.USE_ENGINEERING_SMART_ROUTING
    )


def engineering_generate(
    prompt: str,
    *,
    text: str,
    discipline: str,
    complexity: str | None = None,
    client: Any = None,
    timeout: int | None = None,
    llm_model: str | None = None,
) -> tuple[str, str]:
    from models.ollama_client import OllamaClient

    llm = client or OllamaClient(timeout=timeout or 120)
    if not engineering_routing_enabled():
        from core.llm_override import get_llm_model_override

        override = get_llm_model_override()
        if override:
            return llm.generate(prompt, model=override)
        return llm.generate(prompt)

    router = get_model_router()
    cx = complexity or estimate_engineering_complexity(text, discipline)
    task_type = router.resolve_engineering_task_type(cx)
    ctx = {
        "text": text,
        "input": text,
        "complexity": cx,
        "discipline": discipline,
        "module": "agent",
    }
    model = router.get_model(task_type, ctx)
    fallbacks = router.get_fallback_models(task_type, ctx)

    from core.llm_override import get_llm_model_override, resolve_llm_model
    from core.runtime.ollama_concurrency import resolve_llm_stream_config

    override = resolve_llm_model(llm_model) or get_llm_model_override()
    if override:
        model = override
    stream_timeout, ollama_options, fallbacks, _, effective = resolve_llm_stream_config(
        primary_model=model,
        fallback_models=fallbacks,
        llm_model=llm_model,
    )
    model = effective or model
    effective_timeout = timeout or stream_timeout
    llm = client or OllamaClient(timeout=effective_timeout)

    if override:
        return llm.generate(
            prompt,
            model=model,
            fallback_models=fallbacks or None,
            options=ollama_options or None,
        )

    return routed_generate(
        prompt,
        task_type,
        context=ctx,
        module="agent",
        discipline=discipline,
        client=llm,
        timeout=effective_timeout,
    )


def engineering_stream_models(
    text: str,
    discipline: str,
    *,
    complexity: str | None = None,
    llm_model: str | None = None,
) -> tuple[str, list[str], str]:
    if not engineering_routing_enabled():
        from config.settings import OLLAMA_LLM_MODEL
        from core.llm_override import resolve_llm_model

        override = resolve_llm_model(llm_model)
        if override:
            fb = settings.OLLAMA_LLM_FALLBACK_MODEL
            fallbacks = [fb] if fb and fb != override else []
            return override, fallbacks, "user_override"

        fb = settings.OLLAMA_LLM_FALLBACK_MODEL
        fallbacks = [fb] if fb and fb != OLLAMA_LLM_MODEL else []
        return OLLAMA_LLM_MODEL, fallbacks, "engineering_fallback"

    from core.llm_override import resolve_llm_model

    router = get_model_router()
    cx = complexity or estimate_engineering_complexity(text, discipline)
    task_type = router.resolve_engineering_task_type(cx)
    ctx = {
        "text": text,
        "input": text,
        "complexity": cx,
        "discipline": discipline,
        "module": "agent",
    }
    override = resolve_llm_model(llm_model)
    if override:
        fallbacks = router.get_fallback_models(task_type, ctx)
        return override, fallbacks, "user_override"
    model, fallbacks, resolved = router.get_optimal_model(
        task_type, complexity=cx, context=ctx
    )
    return model, fallbacks, resolved
