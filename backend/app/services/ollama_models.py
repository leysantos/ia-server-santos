"""Consulta modelos instalados no Ollama local."""

from __future__ import annotations

import requests

from config.settings import OLLAMA_BASE_URL


_LLM_DISPLAY_PRIORITY = (
    "qwen3.6",
    "gemma4",
    "deepseek-r1",
    "qwen3-coder",
    "qwen3:14",
    "qwen3:8",
    "gemma3",
    "qwen2.5-coder",
    "mistral",
    "deepseek-coder",
    "phi3",
)


def _model_display_sort_key(name: str) -> tuple[int, int, str]:
    lower = name.lower()
    for idx, token in enumerate(_LLM_DISPLAY_PRIORITY):
        if token in lower:
            return (0, idx, lower)
    return (1, 0, lower)


def sort_models_for_display(names: list[str]) -> list[str]:
    return sorted(names, key=_model_display_sort_key)


def fetch_installed_models() -> list[str] | None:
    """Retorna nomes dos modelos no Ollama ou None se indisponível."""
    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags",
            timeout=3,
        )
        if not response.ok:
            return None
        data = response.json()
        names = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        return sort_models_for_display(names)
    except Exception:
        return None


def fetch_llm_models() -> list[str]:
    """Modelos de completion (exclui embeddings)."""
    installed = fetch_installed_models() or []
    return [m for m in installed if "embed" not in m.lower()]


def normalize_model_label(name: str) -> str:
    return name.removesuffix(":latest")
