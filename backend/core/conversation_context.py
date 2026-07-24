"""Monta contexto multi-turn para chat contínuo."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from core.database.service import list_thread_turns

_THREAD_MARKER = "NOVA MENSAGEM DO USUÁRIO:\n"
_THREAD_HEADER = "CONTEXTO MULTI-TURN (continuidade obrigatória):\n"


def compose_thread_input(
    text: str,
    conversation_id: Optional[str] = None,
    user_id=None,
    db: Optional[Session] = None,
) -> str:
    """
    Injeta histórico compacto antes da nova mensagem.

    Prioriza dados do usuário (dimensões, cargas, fck…) e encurta respostas
    longas do assistente para não estourar a janela do LLM.
    """
    if not conversation_id:
        return text

    turns = list_thread_turns(conversation_id, limit=8, user_id=user_id, db=db)
    if not turns:
        return text

    prior_users = [t["content"] for t in turns if t["role"] == "user"]
    prior_assistants = [t["content"] for t in turns if t["role"] == "assistant"]

    user_block = "\n\n".join(f"- {u}" for u in prior_users) if prior_users else "(nenhum)"
    # Só as 2 últimas respostas — referência; dados do usuário mandam.
    assistant_block = (
        "\n\n".join(f"- {a}" for a in prior_assistants[-2:])
        if prior_assistants
        else "(nenhuma)"
    )

    return (
        f"{_THREAD_HEADER}"
        "Os dados abaixo JÁ FORAM INFORMADOS. Use-os na resposta. "
        "NÃO peça de novo dimensões, vão, carga, fck, cobrimento ou outros "
        "parâmetros que já apareçam em DADOS ANTERIORES.\n\n"
        "DADOS E PEDIDOS ANTERIORES DO USUÁRIO:\n"
        f"{user_block}\n\n"
        "TRECHOS DAS RESPOSTAS ANTERIORES (referência):\n"
        f"{assistant_block}\n\n"
        f"{_THREAD_MARKER}{text}"
    )


def extract_latest_user_message(text: str) -> str:
    """Extrai só a última mensagem do usuário (ignora histórico injetado)."""
    if _THREAD_MARKER in text:
        return text.split(_THREAD_MARKER, 1)[-1].strip()
    return (text or "").strip()


def reattach_thread_prefix(composed_text: str, latest_segment: str) -> str:
    """Reaplica o prefixo de histórico a um segmento (ex.: plano mixed)."""
    if _THREAD_MARKER not in composed_text:
        return latest_segment
    prefix = composed_text.split(_THREAD_MARKER, 1)[0] + _THREAD_MARKER
    return f"{prefix}{latest_segment}"


def build_assistant_meta(response: dict) -> dict:
    extra = response.get("extra") or {}
    return {
        "discipline": response.get("discipline"),
        "agent": response.get("agent"),
        "llm_model": extra.get("llm_model") or extra.get("model"),
        "extra": extra,
    }
