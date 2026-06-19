import requests
from sqlalchemy import text

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


class HealthService:
    """Verifica status dos componentes do sistema."""

    def check(self) -> dict:
        return {
            "status": "ok",
            "database": self._check_database(),
            "rag_version": RAG_VERSION,
            "rag_indexed_chunks": self._rag_chunks(),
            "ollama": self._check_ollama(),
            "models": {
                "chat": OLLAMA_CHAT_MODEL,
                "engineering": OLLAMA_LLM_MODEL,
                "fallback": OLLAMA_LLM_FALLBACK_MODEL,
                "embed": OLLAMA_EMBED_MODEL,
            },
        }

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
