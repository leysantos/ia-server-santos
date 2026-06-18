"""
Service — camada de negócio sobre o repository.

API pública de persistência, pronta para FastAPI.
"""

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.database.connection import is_db_enabled, session_scope
from core.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)


def _parse_uuid(value: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def save_conversation(
    input_text: str,
    mode: str = "single",
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    """
    Persiste uma conversa e retorna representação serializada.
    """
    if not is_db_enabled():
        return None

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            conversation = repo.create_conversation(input_text=input_text, mode=mode)
            db.commit()
            return DatabaseRepository.serialize_conversation(conversation)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            conversation = repo.create_conversation(input_text=input_text, mode=mode)
            return DatabaseRepository.serialize_conversation(conversation)
    except Exception as exc:
        logger.warning("Falha ao salvar conversation: %s", exc)
        return None


def save_orchestrator_log(
    input_text: str,
    disciplines: list[str],
    final_report: str,
    synthesis: dict,
    use_rag: bool = True,
    agent_count: int = 0,
    conversation_id: Optional[str | uuid.UUID] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    """Persiste log de execução do orchestrator."""
    if not is_db_enabled():
        return None

    try:
        conv_id = _parse_uuid(conversation_id)

        if db is not None:
            repo = DatabaseRepository(db)
            log = repo.create_orchestrator_log(
                input_text=input_text,
                disciplines=disciplines,
                final_report=final_report,
                synthesis=synthesis,
                use_rag=use_rag,
                agent_count=agent_count,
                conversation_id=conv_id,
            )
            db.commit()
            return DatabaseRepository.serialize_orchestrator_log(log)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            log = repo.create_orchestrator_log(
                input_text=input_text,
                disciplines=disciplines,
                final_report=final_report,
                synthesis=synthesis,
                use_rag=use_rag,
                agent_count=agent_count,
                conversation_id=conv_id,
            )
            return DatabaseRepository.serialize_orchestrator_log(log)
    except Exception as exc:
        logger.warning("Falha ao salvar orchestrator_log: %s", exc)
        return None


def save_agent_run(
    route_result: dict,
    response: dict,
    conversation_id: Optional[str | uuid.UUID] = None,
    orchestrator_log_id: Optional[str | uuid.UUID] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    """Persiste execução individual de agente (dispatcher)."""
    if not is_db_enabled():
        return None

    try:
        input_text = route_result.get("input", "")
        discipline = response.get("discipline") or route_result.get("discipline")
        agent_name = response.get("agent") or route_result.get("agent")
        result_text = response.get("result") or response.get("response")
        had_context = bool(route_result.get("context"))
        extra = response.get("extra")

        conv_id = _parse_uuid(
            conversation_id or route_result.get("_conversation_id")
        )
        log_id = _parse_uuid(
            orchestrator_log_id or route_result.get("_orchestrator_log_id")
        )

        if db is not None:
            repo = DatabaseRepository(db)
            run = repo.create_agent_run(
                input_text=input_text,
                discipline=discipline,
                agent_name=agent_name,
                result_text=result_text,
                had_context=had_context,
                extra=extra,
                response_payload=response,
                conversation_id=conv_id,
                orchestrator_log_id=log_id,
            )
            db.commit()
            return DatabaseRepository.serialize_agent_run(run)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            run = repo.create_agent_run(
                input_text=input_text,
                discipline=discipline,
                agent_name=agent_name,
                result_text=result_text,
                had_context=had_context,
                extra=extra,
                response_payload=response,
                conversation_id=conv_id,
                orchestrator_log_id=log_id,
            )
            return DatabaseRepository.serialize_agent_run(run)
    except Exception as exc:
        logger.warning("Falha ao salvar agent_run: %s", exc)
        return None


def get_history(
    limit: int = 50,
    conversation_id: Optional[str | uuid.UUID] = None,
    db: Optional[Session] = None,
) -> list[dict[str, Any]]:
    """Retorna histórico de conversas com logs e execuções de agentes."""
    if not is_db_enabled():
        return []

    try:
        conv_id = _parse_uuid(conversation_id)

        if db is not None:
            repo = DatabaseRepository(db)
            conversations = repo.get_history(limit=limit, conversation_id=conv_id)
            return [repo.serialize_conversation(c) for c in conversations]

        with session_scope() as session:
            repo = DatabaseRepository(session)
            conversations = repo.get_history(limit=limit, conversation_id=conv_id)
            return [repo.serialize_conversation(c) for c in conversations]
    except Exception as exc:
        logger.warning("Falha ao obter history: %s", exc)
        return []
