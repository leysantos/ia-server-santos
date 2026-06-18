import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="single")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    orchestrator_logs: Mapped[list["OrchestratorLog"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class OrchestratorLog(Base):
    __tablename__ = "orchestrator_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    disciplines: Mapped[list | None] = mapped_column(JSON, nullable=True)
    final_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    synthesis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    use_rag: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    agent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation | None"] = relationship(
        back_populates="orchestrator_logs"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="orchestrator_log",
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True
    )
    orchestrator_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orchestrator_logs.id"),
        nullable=True,
        index=True,
    )
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discipline: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    had_context: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation | None"] = relationship(
        back_populates="agent_runs"
    )
    orchestrator_log: Mapped["OrchestratorLog | None"] = relationship(
        back_populates="agent_runs"
    )
