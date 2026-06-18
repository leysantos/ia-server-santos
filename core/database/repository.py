"""
Repository — acesso direto ao PostgreSQL (SQLAlchemy ORM).
"""

import uuid
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from core.database.models import AgentRun, Conversation, OrchestratorLog


class DatabaseRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- conversations ---

    def create_conversation(
        self,
        input_text: str,
        mode: str = "single",
    ) -> Conversation:
        conversation = Conversation(input_text=input_text, mode=mode)
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def get_conversation(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        return self.db.get(Conversation, conversation_id)

    # --- orchestrator_logs ---

    def create_orchestrator_log(
        self,
        input_text: str,
        disciplines: list[str],
        final_report: str,
        synthesis: dict,
        use_rag: bool,
        agent_count: int,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> OrchestratorLog:
        log = OrchestratorLog(
            conversation_id=conversation_id,
            input_text=input_text,
            disciplines=disciplines,
            final_report=final_report,
            synthesis=synthesis,
            use_rag=use_rag,
            agent_count=agent_count,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def get_orchestrator_log(self, log_id: uuid.UUID) -> Optional[OrchestratorLog]:
        return self.db.get(OrchestratorLog, log_id)

    # --- agent_runs ---

    def create_agent_run(
        self,
        input_text: str,
        discipline: Optional[str],
        agent_name: Optional[str],
        result_text: Optional[str],
        had_context: bool,
        extra: Optional[dict],
        response_payload: Optional[dict],
        conversation_id: Optional[uuid.UUID] = None,
        orchestrator_log_id: Optional[uuid.UUID] = None,
    ) -> AgentRun:
        run = AgentRun(
            conversation_id=conversation_id,
            orchestrator_log_id=orchestrator_log_id,
            agent_name=agent_name,
            discipline=discipline,
            input_text=input_text,
            result_text=result_text,
            had_context=had_context,
            extra=extra,
            response_payload=response_payload,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def list_agent_runs(
        self,
        conversation_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        stmt = select(AgentRun).order_by(desc(AgentRun.created_at)).limit(limit)
        if conversation_id:
            stmt = stmt.where(AgentRun.conversation_id == conversation_id)
        return list(self.db.scalars(stmt).all())

    # --- history ---

    def get_history(
        self,
        limit: int = 50,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        if conversation_id:
            stmt = stmt.where(Conversation.id == conversation_id)
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def serialize_conversation(conversation: Conversation) -> dict[str, Any]:
        return {
            "id": str(conversation.id),
            "input_text": conversation.input_text,
            "mode": conversation.mode,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "orchestrator_logs": [
                DatabaseRepository.serialize_orchestrator_log(log)
                for log in conversation.orchestrator_logs
            ],
            "agent_runs": [
                DatabaseRepository.serialize_agent_run(run)
                for run in conversation.agent_runs
            ],
        }

    @staticmethod
    def serialize_orchestrator_log(log: OrchestratorLog) -> dict[str, Any]:
        return {
            "id": str(log.id),
            "conversation_id": str(log.conversation_id) if log.conversation_id else None,
            "input_text": log.input_text,
            "disciplines": log.disciplines,
            "final_report": log.final_report,
            "synthesis": log.synthesis,
            "use_rag": log.use_rag,
            "agent_count": log.agent_count,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    @staticmethod
    def serialize_agent_run(run: AgentRun) -> dict[str, Any]:
        return {
            "id": str(run.id),
            "conversation_id": str(run.conversation_id) if run.conversation_id else None,
            "orchestrator_log_id": str(run.orchestrator_log_id) if run.orchestrator_log_id else None,
            "agent_name": run.agent_name,
            "discipline": run.discipline,
            "input_text": run.input_text,
            "result_text": run.result_text,
            "had_context": run.had_context,
            "extra": run.extra,
            "response_payload": run.response_payload,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
