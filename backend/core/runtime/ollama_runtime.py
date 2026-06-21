"""Consulta e controle de modelos Ollama carregados em memória/VRAM."""

from __future__ import annotations

import logging
from typing import Any

import requests

from config.settings import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return OLLAMA_BASE_URL.rstrip("/")


def list_running_models() -> dict[str, Any]:
    """Modelos atualmente residentes (GET /api/ps)."""
    try:
        response = requests.get(f"{_base_url()}/api/ps", timeout=(3, 8))
        response.raise_for_status()
        data = response.json()
        models = []
        for row in data.get("models") or []:
            size_vram = row.get("size_vram") or 0
            models.append(
                {
                    "name": row.get("name") or row.get("model") or "—",
                    "size_vram_mb": round(size_vram / (1024 * 1024), 1) if size_vram else 0,
                    "context_length": row.get("context_length"),
                    "expires_at": row.get("expires_at"),
                }
            )
        return {"reachable": True, "models": models, "count": len(models)}
    except Exception as exc:
        logger.warning("Ollama /api/ps falhou: %s", exc)
        return {"reachable": False, "models": [], "count": 0, "error": str(exc)}


def unload_model(model: str) -> dict[str, Any]:
    """Descarrega um modelo da VRAM (keep_alive=0). Interrompe inferências em curso."""
    name = (model or "").strip()
    if not name:
        return {"ok": False, "error": "modelo inválido"}

    try:
        response = requests.post(
            f"{_base_url()}/api/generate",
            json={"model": name, "prompt": "", "keep_alive": 0},
            timeout=(3, 30),
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "ok": True,
            "model": name,
            "done_reason": payload.get("done_reason"),
        }
    except Exception as exc:
        logger.warning("Ollama unload %s falhou: %s", name, exc)
        return {"ok": False, "model": name, "error": str(exc)}


def unload_all_models() -> dict[str, Any]:
    """Descarrega todos os modelos listados em /api/ps."""
    running = list_running_models()
    if not running.get("reachable"):
        return {"ok": False, "unloaded": [], "error": running.get("error") or "Ollama indisponível"}

    unloaded: list[str] = []
    errors: list[dict[str, str]] = []
    for row in running.get("models") or []:
        name = row.get("name")
        if not name:
            continue
        result = unload_model(name)
        if result.get("ok"):
            unloaded.append(name)
        else:
            errors.append({"model": name, "error": result.get("error") or "falha"})

    return {"ok": len(errors) == 0, "unloaded": unloaded, "errors": errors}
