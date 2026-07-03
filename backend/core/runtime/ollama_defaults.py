"""Opções padrão Ollama (contexto, keep_alive) centralizadas."""

from __future__ import annotations

from typing import Any

from config import settings


def ollama_keep_alive() -> str:
    return str(getattr(settings, "OLLAMA_KEEP_ALIVE", "15m") or "15m")


def default_llm_options(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "num_ctx": int(getattr(settings, "OLLAMA_NUM_CTX", 8192)),
    }
    if overrides:
        opts.update(overrides)
    return opts


def merge_llm_options(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mescla defaults com opções específicas da chamada."""
    return default_llm_options(overrides)
