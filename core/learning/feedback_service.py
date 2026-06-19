"""
Learning Loop v1 — coleta de feedback e observações de execução.

Fire-and-forget: falhas de persistência apenas geram warning no log.
Não altera RAG, agentes nem fluxo principal.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from core.database.connection import is_db_enabled, session_scope
from core.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)


def _parse_uuid(value: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _validate_rating(rating: Optional[int]) -> Optional[int]:
    if rating is None:
        return None
    if not 1 <= rating <= 5:
        raise ValueError("rating deve estar entre 1 e 5")
    return rating


def record_agent_execution(
    *,
    agent_name: str,
    discipline: Optional[str],
    input_text: str,
    response_text: Optional[str],
    conversation_id: Optional[str | uuid.UUID] = None,
) -> None:
    """
    Registra execução automática de agente (sem rating).
    Chamado pelo dispatcher após cada resposta.
    """
    if not is_db_enabled():
        return

    try:
        conv_id = _parse_uuid(conversation_id)
        with session_scope() as session:
            repo = DatabaseRepository(session)
            repo.create_agent_feedback(
                agent_name=agent_name or "unknown_agent",
                discipline=discipline,
                input_text=input_text or "",
                response_text=response_text,
                conversation_id=conv_id,
            )
    except Exception as exc:
        logger.warning("Learning Loop: falha ao registrar execução do agente: %s", exc)


def record_orchestrator_summary(
    *,
    input_text: str,
    response_text: str,
    conversation_id: Optional[str | uuid.UUID] = None,
) -> None:
    """Registra síntese multidisciplinar do orchestrator."""
    record_agent_execution(
        agent_name="orchestrator",
        discipline="MULTI",
        input_text=input_text,
        response_text=response_text,
        conversation_id=conversation_id,
    )


def save_feedback(
    *,
    conversation_id: Optional[str | uuid.UUID] = None,
    agent_name: str,
    discipline: Optional[str] = None,
    input_text: Optional[str] = None,
    response_text: Optional[str] = None,
    rating: Optional[int] = None,
    feedback_text: Optional[str] = None,
    corrected_answer: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Salva ou enriquece feedback explícito do usuário (POST /feedback).

    Se existir registro recente para conversation_id + agent_name, atualiza rating.
    Caso contrário, cria novo registro.
    """
    if not is_db_enabled():
        logger.warning("Learning Loop: DB desabilitado — feedback não salvo")
        return None

    try:
        rating = _validate_rating(rating)
        conv_id = _parse_uuid(conversation_id)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = None

            if conv_id and agent_name:
                row = repo.get_latest_feedback(conv_id, agent_name)

            if row and (rating is not None or feedback_text or corrected_answer):
                if rating is not None:
                    row.rating = rating
                if feedback_text is not None:
                    row.feedback_text = feedback_text
                if corrected_answer is not None:
                    row.corrected_answer = corrected_answer
                session.flush()
            else:
                row = repo.create_agent_feedback(
                    conversation_id=conv_id,
                    agent_name=agent_name,
                    discipline=discipline,
                    input_text=input_text or "",
                    response_text=response_text,
                    rating=rating,
                    feedback_text=feedback_text,
                    corrected_answer=corrected_answer,
                )

            return DatabaseRepository.serialize_agent_feedback(row)
    except ValueError:
        raise
    except Exception as exc:
        logger.warning("Learning Loop: falha ao salvar feedback: %s", exc)
        return None


def get_feedback_by_agent(agent_name: str, limit: int = 50) -> list[dict[str, Any]]:
    """Lista feedback e observações por agente."""
    if not is_db_enabled():
        return []

    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            rows = repo.list_feedback_by_agent(agent_name, limit=limit)
            return [DatabaseRepository.serialize_agent_feedback(r) for r in rows]
    except Exception as exc:
        logger.warning("Learning Loop: falha ao listar feedback: %s", exc)
        return []


def get_low_quality_responses(threshold: int = 3, limit: int = 50) -> list[dict[str, Any]]:
    """Respostas com rating <= threshold (qualidade baixa)."""
    if not is_db_enabled():
        return []

    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            rows = repo.list_low_quality_responses(threshold=threshold, limit=limit)
            return [DatabaseRepository.serialize_agent_feedback(r) for r in rows]
    except Exception as exc:
        logger.warning("Learning Loop: falha ao listar baixa qualidade: %s", exc)
        return []
