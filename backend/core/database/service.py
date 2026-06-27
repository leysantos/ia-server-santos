"""
Service — camada de negócio sobre o repository.

API pública de persistência, pronta para FastAPI.
"""

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.database.connection import is_db_enabled, session_scope
from core.database.conversation_access import user_owns_conversation
from core.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)

_SENTINEL = object()


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
    title: Optional[str] = None,
    project_id: Optional[str | uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
) -> Optional[dict[str, Any]]:
    """
    Persiste uma conversa e retorna representação serializada.
    """
    if not is_db_enabled():
        return None

    proj_id = _parse_uuid(project_id)

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            conversation = repo.create_conversation(
                input_text=input_text,
                mode=mode,
                title=title,
                project_id=proj_id,
                user_id=user_id,
            )
            db.commit()
            return DatabaseRepository.serialize_conversation_summary(conversation)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            conversation = repo.create_conversation(
                input_text=input_text,
                mode=mode,
                title=title,
                project_id=proj_id,
                user_id=user_id,
            )
            return DatabaseRepository.serialize_conversation_summary(conversation)
    except Exception as exc:
        logger.warning("Falha ao salvar conversation: %s", exc)
        return None


def ensure_conversation(
    text: str,
    mode: str = "single",
    conversation_id: Optional[str | uuid.UUID] = None,
    project_id: Optional[str | uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    """
    Retorna conversa existente ou cria nova para multi-turn chat.
    """
    if not is_db_enabled():
        return None

    conv_id = _parse_uuid(conversation_id)
    proj_id = _parse_uuid(project_id)

    def _run(session: Session) -> Optional[dict[str, Any]]:
        repo = DatabaseRepository(session)
        if conv_id:
            conversation = repo.get_conversation(conv_id)
            if conversation:
                if not user_owns_conversation(conversation, user_id):
                    return None
                if proj_id and conversation.project_id != proj_id:
                    repo.update_conversation(conversation, project_id=proj_id)
                return DatabaseRepository.serialize_conversation_summary(conversation)
        conversation = repo.create_conversation(
            input_text=text,
            mode=mode,
            project_id=proj_id,
            user_id=user_id,
        )
        return DatabaseRepository.serialize_conversation_summary(conversation)

    try:
        if db is not None:
            result = _run(db)
            db.commit()
            return result
        with session_scope() as session:
            return _run(session)
    except Exception as exc:
        logger.warning("Falha em ensure_conversation: %s", exc)
        return None


def append_conversation_messages(
    conversation_id: str | uuid.UUID,
    user_text: str,
    assistant_text: str,
    assistant_meta: Optional[dict] = None,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> bool:
    """Persiste par user/assistant na conversa."""
    if not is_db_enabled():
        return False

    conv_id = _parse_uuid(conversation_id)
    if not conv_id:
        return False

    def _run(session: Session) -> bool:
        repo = DatabaseRepository(session)
        conversation = repo.get_conversation(conv_id)
        if not conversation or not user_owns_conversation(conversation, user_id):
            return False
        repo.create_message(conv_id, "user", user_text)
        repo.create_message(conv_id, "assistant", assistant_text, meta=assistant_meta)
        return True

    try:
        if db is not None:
            ok = _run(db)
            db.commit()
            return ok
        with session_scope() as session:
            return _run(session)
    except Exception as exc:
        logger.warning("Falha ao salvar messages: %s", exc)
        return False


def build_thread_context(
    conversation_id: str | uuid.UUID,
    limit: int = 12,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> str:
    """Monta histórico textual para continuidade multi-turn."""
    if not is_db_enabled():
        return ""

    conv_id = _parse_uuid(conversation_id)
    if not conv_id:
        return ""

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            conversation = repo.get_conversation(conv_id)
            if not conversation or not user_owns_conversation(conversation, user_id):
                return ""
            messages = repo.list_messages(conv_id, limit=limit)
        else:
            with session_scope() as session:
                repo = DatabaseRepository(session)
                conversation = repo.get_conversation(conv_id)
                if not conversation or not user_owns_conversation(conversation, user_id):
                    return ""
                messages = repo.list_messages(conv_id, limit=limit)

        if not messages:
            return ""

        lines: list[str] = []
        for msg in messages:
            label = "Usuário" if msg.role == "user" else "Assistente"
            content = (msg.content or "").strip()
            if content:
                lines.append(f"{label}: {content[:3000]}")
        return "\n\n".join(lines)
    except Exception as exc:
        logger.warning("Falha ao montar thread context: %s", exc)
        return ""


def list_conversations(
    limit: int = 50,
    project_id: Optional[str | uuid.UUID] = None,
    unassigned_only: bool = False,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> list[dict[str, Any]]:
    if not is_db_enabled():
        return []

    proj_id = _parse_uuid(project_id)

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            rows = repo.list_conversations(
                limit=limit,
                project_id=proj_id,
                unassigned_only=unassigned_only,
                user_id=user_id,
            )
            return [DatabaseRepository.serialize_conversation_summary(c) for c in rows]

        with session_scope() as session:
            repo = DatabaseRepository(session)
            rows = repo.list_conversations(
                limit=limit,
                project_id=proj_id,
                unassigned_only=unassigned_only,
                user_id=user_id,
            )
            return [DatabaseRepository.serialize_conversation_summary(c) for c in rows]
    except Exception as exc:
        logger.warning("Falha ao listar conversations: %s", exc)
        return []


def get_conversation_detail(
    conversation_id: str | uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    if not is_db_enabled():
        return None

    conv_id = _parse_uuid(conversation_id)
    if not conv_id:
        return None

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            conversation = repo.get_conversation_detail(conv_id)
            if not conversation or not user_owns_conversation(conversation, user_id):
                return None
            return DatabaseRepository.serialize_conversation(conversation)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            conversation = repo.get_conversation_detail(conv_id)
            if not conversation or not user_owns_conversation(conversation, user_id):
                return None
            return DatabaseRepository.serialize_conversation(conversation)
    except Exception as exc:
        logger.warning("Falha ao obter conversation: %s", exc)
        return None


def update_conversation_record(
    conversation_id: str | uuid.UUID,
    *,
    title: Optional[str] = None,
    project_id: Optional[str | uuid.UUID | None] = _SENTINEL,  # noqa: ANN001
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    if not is_db_enabled():
        return None

    conv_id = _parse_uuid(conversation_id)
    if not conv_id:
        return None

    fields: dict[str, Any] = {}
    if title is not None:
        fields["title"] = title
    if project_id is not _SENTINEL:
        fields["project_id"] = _parse_uuid(project_id) if project_id else None

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            conversation = repo.get_conversation(conv_id)
            if not conversation or not user_owns_conversation(conversation, user_id):
                return None
            repo.update_conversation(conversation, **fields)
            db.commit()
            return DatabaseRepository.serialize_conversation_summary(conversation)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            conversation = repo.get_conversation(conv_id)
            if not conversation or not user_owns_conversation(conversation, user_id):
                return None
            repo.update_conversation(conversation, **fields)
            return DatabaseRepository.serialize_conversation_summary(conversation)
    except Exception as exc:
        logger.warning("Falha ao atualizar conversation: %s", exc)
        return None


def delete_conversation_record(
    conversation_id: str | uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> bool:
    if not is_db_enabled():
        return False

    conv_id = _parse_uuid(conversation_id)
    if not conv_id:
        return False

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            conversation = repo.get_conversation(conv_id)
            if not conversation or not user_owns_conversation(conversation, user_id):
                return False
            ok = repo.delete_conversation(conv_id)
            db.commit()
            return ok
        with session_scope() as session:
            repo = DatabaseRepository(session)
            conversation = repo.get_conversation(conv_id)
            if not conversation or not user_owns_conversation(conversation, user_id):
                return False
            return repo.delete_conversation(conv_id)
    except Exception as exc:
        logger.warning("Falha ao deletar conversation: %s", exc)
        return False


def search_workspace(
    query: str,
    limit: int = 30,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Busca projetos e conversas por título, texto ou mensagens."""
    if not is_db_enabled() or not query.strip():
        return {"projects": [], "conversations": []}

    q = query.strip()
    proj_limit = min(limit, 20)
    conv_limit = min(limit, 40)

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            projects = repo.search_projects(q, limit=proj_limit)
            conversations = repo.search_conversations(q, limit=conv_limit, user_id=user_id)
            return {
                "projects": [DatabaseRepository.serialize_project(p) for p in projects],
                "conversations": [
                    DatabaseRepository.serialize_conversation_summary(c) for c in conversations
                ],
            }

        with session_scope() as session:
            repo = DatabaseRepository(session)
            projects = repo.search_projects(q, limit=proj_limit)
            conversations = repo.search_conversations(q, limit=conv_limit, user_id=user_id)
            return {
                "projects": [DatabaseRepository.serialize_project(p) for p in projects],
                "conversations": [
                    DatabaseRepository.serialize_conversation_summary(c) for c in conversations
                ],
            }
    except Exception as exc:
        logger.warning("Falha em search_workspace: %s", exc)
        return {"projects": [], "conversations": []}


def list_projects(limit: int = 50, db: Optional[Session] = None) -> list[dict[str, Any]]:
    if not is_db_enabled():
        return []

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            rows = repo.list_projects(limit=limit)
            return [DatabaseRepository.serialize_project(p) for p in rows]

        with session_scope() as session:
            repo = DatabaseRepository(session)
            rows = repo.list_projects(limit=limit)
            return [DatabaseRepository.serialize_project(p) for p in rows]
    except Exception as exc:
        logger.warning("Falha ao listar projects: %s", exc)
        return []


def create_project_record(
    name: str,
    description: Optional[str] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    if not is_db_enabled():
        return None

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            project = repo.create_project(name=name, description=description)
            db.commit()
            return DatabaseRepository.serialize_project(project)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            project = repo.create_project(name=name, description=description)
            return DatabaseRepository.serialize_project(project)
    except Exception as exc:
        logger.warning("Falha ao criar project: %s", exc)
        return None


def get_project_detail(
    project_id: str | uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    if not is_db_enabled():
        return None

    pid = _parse_uuid(project_id)
    if not pid:
        return None

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            project = repo.get_project_detail(pid)
            if not project:
                return None
            return DatabaseRepository.serialize_project(
                project, include_children=True, user_id=user_id
            )

        with session_scope() as session:
            repo = DatabaseRepository(session)
            project = repo.get_project_detail(pid)
            if not project:
                return None
            return DatabaseRepository.serialize_project(
                project, include_children=True, user_id=user_id
            )
    except Exception as exc:
        logger.warning("Falha ao obter project: %s", exc)
        return None


def update_project_record(
    project_id: str | uuid.UUID,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    if not is_db_enabled():
        return None

    pid = _parse_uuid(project_id)
    if not pid:
        return None

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            project = repo.get_project(pid)
            if not project:
                return None
            repo.update_project(project, name=name, description=description)
            db.commit()
            return DatabaseRepository.serialize_project(project)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            project = repo.get_project(pid)
            if not project:
                return None
            repo.update_project(project, name=name, description=description)
            return DatabaseRepository.serialize_project(project)
    except Exception as exc:
        logger.warning("Falha ao atualizar project: %s", exc)
        return None


def delete_project_record(project_id: str | uuid.UUID, db: Optional[Session] = None) -> bool:
    if not is_db_enabled():
        return False

    pid = _parse_uuid(project_id)
    if not pid:
        return False

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            ok = repo.delete_project(pid)
            db.commit()
            return ok
        with session_scope() as session:
            repo = DatabaseRepository(session)
            return repo.delete_project(pid)
    except Exception as exc:
        logger.warning("Falha ao deletar project: %s", exc)
        return False


def add_project_file_record(
    project_id: str | uuid.UUID,
    filename: str,
    storage_path: str,
    content_type: Optional[str] = None,
    size_bytes: Optional[int] = None,
    db: Optional[Session] = None,
) -> Optional[dict[str, Any]]:
    if not is_db_enabled():
        return None

    pid = _parse_uuid(project_id)
    if not pid:
        return None

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            row = repo.create_project_file(
                project_id=pid,
                filename=filename,
                storage_path=storage_path,
                content_type=content_type,
                size_bytes=size_bytes,
            )
            db.commit()
            return DatabaseRepository.serialize_project_file(row)

        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_project_file(
                project_id=pid,
                filename=filename,
                storage_path=storage_path,
                content_type=content_type,
                size_bytes=size_bytes,
            )
            return DatabaseRepository.serialize_project_file(row)
    except Exception as exc:
        logger.warning("Falha ao salvar project file: %s", exc)
        return None


def delete_project_file_record(file_id: str | uuid.UUID, db: Optional[Session] = None) -> bool:
    if not is_db_enabled():
        return False

    fid = _parse_uuid(file_id)
    if not fid:
        return False

    try:
        if db is not None:
            repo = DatabaseRepository(db)
            ok = repo.delete_project_file(fid)
            db.commit()
            return ok
        with session_scope() as session:
            repo = DatabaseRepository(session)
            return repo.delete_project_file(fid)
    except Exception as exc:
        logger.warning("Falha ao deletar project file: %s", exc)
        return False


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
            serialized = DatabaseRepository.serialize_orchestrator_log(log)
            try:
                from core.project_memory.service import record_orchestrator_completion

                record_orchestrator_completion(
                    input_text=input_text,
                    disciplines=disciplines,
                    synthesis=synthesis,
                    conversation_id=conv_id,
                    orchestrator_log_id=log.id,
                    db=db,
                )
            except Exception:
                pass
            return serialized

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
            serialized = DatabaseRepository.serialize_orchestrator_log(log)
            try:
                from core.project_memory.service import record_orchestrator_completion

                record_orchestrator_completion(
                    input_text=input_text,
                    disciplines=disciplines,
                    synthesis=synthesis,
                    conversation_id=conv_id,
                    orchestrator_log_id=log.id,
                    db=session,
                )
            except Exception:
                pass
            return serialized
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
    user_id: Optional[uuid.UUID] = None,
    db: Optional[Session] = None,
) -> list[dict[str, Any]]:
    """Retorna histórico de conversas com logs e execuções de agentes."""
    if not is_db_enabled():
        return []

    try:
        conv_id = _parse_uuid(conversation_id)

        if db is not None:
            repo = DatabaseRepository(db)
            if conv_id:
                conversation = repo.get_conversation_detail(conv_id)
                if conversation and user_owns_conversation(conversation, user_id):
                    return [DatabaseRepository.serialize_conversation(conversation)]
                return []
            conversations = repo.get_history(
                limit=limit, conversation_id=conv_id, user_id=user_id
            )
            return [
                DatabaseRepository.serialize_conversation(c, include_audit=True)
                for c in conversations
            ]

        with session_scope() as session:
            repo = DatabaseRepository(session)
            if conv_id:
                conversation = repo.get_conversation_detail(conv_id)
                if conversation and user_owns_conversation(conversation, user_id):
                    return [DatabaseRepository.serialize_conversation(conversation)]
                return []
            conversations = repo.get_history(
                limit=limit, conversation_id=conv_id, user_id=user_id
            )
            return [
                DatabaseRepository.serialize_conversation(c, include_audit=True)
                for c in conversations
            ]
    except Exception as exc:
        logger.warning("Falha ao obter history: %s", exc)
        return []
