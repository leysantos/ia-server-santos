"""Override de modelo LLM por requisição (contextvar)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_llm_override: ContextVar[Optional[str]] = ContextVar("llm_model_override", default=None)

# Alias aceitos no seletor / override → id canônico Gemini
_GEMINI_ALIASES = frozenset(
    {
        "gemini",
        "gemini-3.6",
        "gemini-3.6-flash",
        "gemini-3.6-pro",
        "google-gemini",
    }
)


def is_gemini_model(model: Optional[str]) -> bool:
    """True se o nome aponta para Gemini (cloud), não Ollama."""
    if not model:
        return False
    lower = model.strip().lower()
    if lower in _GEMINI_ALIASES:
        return True
    return lower.startswith("gemini")


def canonical_gemini_model(model: Optional[str] = None) -> str:
    """Resolve alias → GEMINI_MODEL (default gemini-3.6-flash)."""
    from core.inspection_report.gemini_client import resolve_gemini_model

    configured = (resolve_gemini_model() or "gemini-3.6-flash").strip()
    if not model:
        return configured
    lower = model.strip().lower()
    if lower in ("gemini", "gemini-3.6", "google-gemini"):
        return configured
    return model.strip() or configured


def list_cloud_llm_models() -> list[str]:
    """Modelos cloud disponíveis para o seletor (Gemini se API key OK)."""
    try:
        from core.inspection_report.gemini_client import gemini_available, resolve_gemini_model

        if not gemini_available():
            return []
        name = (resolve_gemini_model() or "gemini-3.6-flash").strip()
        return [name] if name else []
    except Exception:
        return []


def normalize_llm_model_choice(model: Optional[str]) -> Optional[str]:
    """Retorna None para auto/vazio; caso contrário o nome do modelo."""
    if not model:
        return None
    cleaned = model.strip()
    if not cleaned or cleaned.lower() == "auto":
        return None
    if is_gemini_model(cleaned):
        return canonical_gemini_model(cleaned)
    return cleaned


def get_llm_model_override() -> Optional[str]:
    return _llm_override.get()


def resolve_llm_model(explicit: Optional[str] = None) -> Optional[str]:
    """
    Modelo efetivo: parâmetro explícito (SSE/stream) tem prioridade sobre ContextVar.
    ContextVar não funciona em generators SSE (Starlette usa thread pool por chunk).
    """
    normalized = normalize_llm_model_choice(explicit)
    if normalized is not None:
        return normalized
    return get_llm_model_override()


@contextmanager
def llm_model_scope(model: Optional[str]) -> Iterator[None]:
    token = _llm_override.set(normalize_llm_model_choice(model))
    try:
        yield
    finally:
        try:
            _llm_override.reset(token)
        except ValueError:
            # Generator SSE — token criado em outro contexto/thread (Starlette thread pool)
            pass
