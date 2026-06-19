import requests
from sqlalchemy import text

from app.services.ollama_models import fetch_installed_models, fetch_llm_models
from config.settings import (
    OLLAMA_BASE_URL,
    OLLAMA_CHAT_MODEL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_LLM_FALLBACK_MODEL,
    OLLAMA_LLM_MODEL,
    RAG_VERSION,
)
from core.database.connection import engine, is_db_enabled
from memory.rag_engine import get_rag_engine


def _normalize_label(name: str) -> str:
    return name.removesuffix(":latest")


class HealthService:
    """Verifica status dos componentes do sistema."""

    def check(self) -> dict:
        installed = fetch_installed_models() or []
        llm_installed = fetch_llm_models()
        return {
            "status": "ok",
            "database": self._check_database(),
            "rag_version": RAG_VERSION,
            "rag_indexed_chunks": self._rag_chunks(),
            "ollama": self._check_ollama(),
            "installed_models": installed,
            "models": {
                "chat": self._resolve_configured(OLLAMA_CHAT_MODEL, llm_installed),
                "engineering": self._resolve_configured(OLLAMA_LLM_MODEL, llm_installed),
                "fallback": self._resolve_configured(
                    OLLAMA_LLM_FALLBACK_MODEL, llm_installed
                ),
                "embed": self._resolve_configured(OLLAMA_EMBED_MODEL, installed),
                "router_enabled": self._router_enabled(),
                "evaluation_enabled": self._evaluation_enabled(),
                "installed_llm": " · ".join(_normalize_label(m) for m in llm_installed),
            },
        }

    @staticmethod
    def _resolve_configured(configured: str, installed: list[str]) -> str:
        if not installed:
            return configured
        if configured in installed:
            return configured
        prefix = configured.split(":")[0]
        for name in installed:
            if name == configured or name.startswith(f"{prefix}:"):
                return name
        return configured

    @staticmethod
    def _router_enabled() -> str:
        from config import settings

        return "true" if settings.USE_MODEL_ROUTER else "false"

    @staticmethod
    def _evaluation_enabled() -> str:
        from config import settings

        return "true" if settings.USE_MODEL_EVALUATION else "false"

    @staticmethod
    def _check_database() -> str:
        if not is_db_enabled():
            return "disabled"

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return "connected"
        except Exception:
            return "unavailable"

    @staticmethod
    def _rag_chunks() -> int:
        try:
            return get_rag_engine().indexed_chunks
        except Exception:
            return 0

    @staticmethod
    def _check_ollama() -> str:
        try:
            response = requests.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3)
            if response.ok:
                return "reachable"
        except Exception:
            pass
        return "unreachable"
