"""Mapa de modelos alinhado ao Ollama instalado no WSL."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable

logger = logging.getLogger(__name__)

# Modelos típicos deste projeto (WSL) — ordem = preferência
INSTALLED_WSL_MODELS: tuple[str, ...] = (
    "gemma4:latest",
    "deepseek-r1:14b",
    "deepseek-coder:latest",
    "mistral:7b",
    "qwen2.5-coder:latest",
    "phi3:mini",
    "gemma3:12b",
    "nomic-embed-text:latest",
    "qwen3-coder:latest",
    "qwen3:14b",
    "qwen3:8b",
)

# Preferências por task_type (primeiro instalado vence)
TASK_MODEL_CANDIDATES: dict[str, tuple[str, ...]] = {
    "chat_simple": ("phi3:mini", "qwen3:8b", "mistral:7b"),
    "intent_layer": ("phi3:mini", "qwen3:8b"),
    "chat_natural": ("mistral:7b", "qwen3:8b", "phi3:mini"),
    "code_generation": ("deepseek-coder:latest", "qwen2.5-coder:latest", "qwen3-coder:latest"),
    "code_understanding": ("qwen2.5-coder:latest", "deepseek-coder:latest", "qwen3-coder:latest"),
    "engineering_primary": ("qwen3:14b", "gemma4:latest", "qwen3:8b", "mistral:7b"),
    "engineering_reasoning": ("deepseek-r1:14b", "qwen3:14b", "gemma4:latest"),
    "engineering_secondary": ("gemma4:latest", "qwen3:14b", "qwen3:8b"),
    "engineering_fallback": ("qwen3:8b", "mistral:7b", "qwen2.5-coder:latest", "phi3:mini"),
    "rag_embedding": ("nomic-embed-text:latest", "nomic-embed-text"),
    "orchestration_synthesis": ("deepseek-r1:14b", "qwen3:14b", "gemma4:latest"),
    "platform_evaluation": ("deepseek-r1:14b", "qwen3:14b", "gemma4:latest"),
    "aed_simulation": ("qwen3:14b", "gemma4:latest", "deepseek-r1:14b"),
    "aed_evaluation": ("deepseek-r1:14b", "qwen3:14b", "gemma4:latest"),
    "budget_wbs_light": ("mistral:7b", "phi3:mini", "qwen3:8b"),
    "budget_wbs": ("qwen2.5-coder:latest", "deepseek-coder:latest", "mistral:7b"),
    "budget_wbs_high": ("qwen3-coder:latest", "deepseek-r1:14b", "qwen2.5-coder:latest"),
    "budget_pricing_light": ("phi3:mini", "mistral:7b"),
    "budget_pricing": ("mistral:7b", "qwen2.5-coder:latest", "qwen3:8b"),
    "budget_pricing_high": ("qwen2.5-coder:latest", "qwen3-coder:latest", "deepseek-r1:14b"),
}


def pick_installed_model(
    candidates: Iterable[str],
    installed: set[str] | frozenset[str],
) -> str | None:
    """Retorna o primeiro candidato presente no Ollama (match exato ou por base name)."""
    installed = set(installed or ())
    if not installed:
        for candidate in candidates:
            if candidate:
                return candidate
        return None

    for candidate in candidates:
        if not candidate:
            continue
        if candidate in installed:
            return candidate
        base = candidate.split(":")[0]
        for name in installed:
            if name == candidate or name.startswith(f"{base}:"):
                return name
    return None


@lru_cache(maxsize=1)
def _cached_installed_models() -> frozenset[str]:
    try:
        from models.ollama_client import OllamaClient

        names = OllamaClient(timeout=10).list_models()
        return frozenset(names)
    except Exception as exc:
        logger.debug("installed models cache miss: %s", exc)
        return frozenset()


def get_installed_model_names(*, force_refresh: bool = False) -> set[str]:
    if force_refresh:
        _cached_installed_models.cache_clear()
    return set(_cached_installed_models())


def resolve_task_model(task_type: str, installed: set[str] | None = None) -> str | None:
    candidates = TASK_MODEL_CANDIDATES.get(task_type)
    if not candidates:
        return None
    names = installed if installed is not None else get_installed_model_names()
    return pick_installed_model(candidates, names)


def build_router_model_map(installed: set[str] | None = None) -> dict[str, str]:
    """Gera model_map só com modelos realmente instalados."""
    names = installed if installed is not None else get_installed_model_names()
    result: dict[str, str] = {}
    for task, candidates in TASK_MODEL_CANDIDATES.items():
        picked = pick_installed_model(candidates, names)
        if picked:
            result[task] = picked
    return result


def filter_installed_models(models: Iterable[str], installed: set[str] | None = None) -> list[str]:
    names = installed if installed is not None else get_installed_model_names()
    if not names:
        return [m for m in models if m]
    out: list[str] = []
    seen: set[str] = set()
    for model in models:
        resolved = pick_installed_model((model,), names) if model else None
        if resolved and resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out
