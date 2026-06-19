"""Monta contexto multi-turn para chat contínuo."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from core.database.service import build_thread_context


def compose_thread_input(
    text: str,
    conversation_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> str:
    """Injeta histórico recente antes da nova mensagem."""
    if not conversation_id:
        return text

    thread = build_thread_context(conversation_id, limit=12, db=db)
    if not thread:
        return text

    return (
        "HISTÓRICO DA CONVERSA (referência — responda à NOVA MENSAGEM abaixo):\n"
        f"{thread}\n\n"
        "NOVA MENSAGEM DO USUÁRIO:\n"
        f"{text}"
    )


def build_assistant_meta(response: dict) -> dict:
    extra = response.get("extra") or {}
    return {
        "discipline": response.get("discipline"),
        "agent": response.get("agent"),
        "llm_model": extra.get("llm_model") or extra.get("model"),
        "extra": extra,
    }
