"""Consulta modelos instalados no Ollama local."""

from __future__ import annotations

import requests

from config.settings import OLLAMA_BASE_URL


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
        return sorted(names, key=str.lower)
    except Exception:
        return None


def fetch_llm_models() -> list[str]:
    """Modelos de completion (exclui embeddings)."""
    installed = fetch_installed_models() or []
    return [m for m in installed if "embed" not in m.lower()]


def normalize_model_label(name: str) -> str:
    return name.removesuffix(":latest")
