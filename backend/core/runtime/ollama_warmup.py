"""Pré-carrega modelos Ollama para evitar cold start na primeira requisição."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def warmup_default_models() -> dict[str, str]:
    """
    Gera um token mínimo nos modelos de chat/engenharia configurados.
    Retorna {modelo: ok|erro}.
    """
    from config import settings
    from core.runtime.ollama_defaults import merge_llm_options
    from models.ollama_client import OllamaClient

    targets = [
        getattr(settings, "OLLAMA_CHAT_MODEL", None),
        getattr(settings, "OLLAMA_LLM_MODEL", None),
    ]
    seen: set[str] = set()
    results: dict[str, str] = {}
    client = OllamaClient(timeout=max(60, int(getattr(settings, "OLLAMA_HEAVY_MODEL_TIMEOUT", 300))))

    for model in targets:
        if not model or model in seen:
            continue
        seen.add(model)
        try:
            _, used = client.generate(
                "Responda apenas: ok",
                model=model,
                options=merge_llm_options({"num_predict": 2}),
            )
            results[used] = "ok"
            logger.info("Ollama warmup OK: %s", used)
        except Exception as exc:
            results[model] = str(exc)[:120]
            logger.warning("Ollama warmup falhou %s: %s", model, exc)

    return results
