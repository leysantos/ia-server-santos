import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
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


class AgentFeedback(Base):
    """Learning Loop v1 — observações de uso e feedback explícito do usuário."""

    __tablename__ = "agent_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    discipline: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CopilotEvaluationRecord(Base):
    """Evaluation Loop v2 — autoavaliação das execuções do Copilot v1."""

    __tablename__ = "copilot_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    intent_accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    plan_quality: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    execution_completeness: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    response_quality: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    scores_detail: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SystemFailure(Base):
    """Self-Improving Loop v1 — registro de falhas detectadas."""

    __tablename__ = "system_failures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    route_decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_used: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    evaluation_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SystemPatch(Base):
    """Self-Improving Loop v1 — propostas de patch versionadas (auditáveis)."""

    __tablename__ = "system_patches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patch_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    patch_version: Mapped[int] = mapped_column(Integer, nullable=False)
    patch_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    impact_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_finding: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AedRun(Base):
    """AED v1 — execuções auditáveis do Autonomous Engineering Designer."""

    __tablename__ = "aed_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    understanding: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    designs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    simulations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    comparison: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    selection: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModelEvaluation(Base):
    """Model Evaluation Loop v1 — comparações primary vs fallback."""

    __tablename__ = "model_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    discipline: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    primary_model: Mapped[str] = mapped_column(String(120), nullable=False)
    fallback_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    winner_model: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    primary_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fallback_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    primary_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fallback_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    primary_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallback_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModelPerformanceProfile(Base):
    """Ranking dinâmico de modelos por task_type + disciplina."""

    __tablename__ = "model_performance_profile"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    discipline: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    win_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_evaluations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    avg_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
