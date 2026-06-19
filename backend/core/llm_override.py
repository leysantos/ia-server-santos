"""Override de modelo LLM por requisição (contextvar)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_llm_override: ContextVar[Optional[str]] = ContextVar("llm_model_override", default=None)


def normalize_llm_model_choice(model: Optional[str]) -> Optional[str]:
    """Retorna None para auto/vazio; caso contrário o nome do modelo."""
    if not model:
        return None
    cleaned = model.strip()
    if not cleaned or cleaned.lower() == "auto":
        return None
    return cleaned


def get_llm_model_override() -> Optional[str]:
    return _llm_override.get()


@contextmanager
def llm_model_scope(model: Optional[str]) -> Iterator[None]:
    token = _llm_override.set(normalize_llm_model_choice(model))
    try:
        yield
    finally:
        _llm_override.reset(token)
