import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    """Workspace — agrupa conversas e arquivos de um empreendimento."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    files: Mapped[list["ProjectFile"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    digital_twins: Mapped[list["ProjectDigitalTwin"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectDigitalTwin.versao.desc()",
    )
    reviews: Mapped[list["ProjectReview"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectReview.version.desc()",
    )
    nonconformities: Mapped[list["ProjectNonconformity"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    activity_events: Mapped[list["ProjectActivityEvent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectActivityEvent.created_at.desc()",
    )
    decisions: Mapped[list["ProjectDecision"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectDecision.created_at.desc()",
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="single")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped["Project | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
    orchestrator_logs: Mapped[list["OrchestratorLog"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ConversationMessage(Base):
    """Mensagens ordenadas de uma conversa (multi-turn chat)."""

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class ProjectFile(Base):
    """Arquivo anexado a um projeto (PDF, planilha, etc.)."""

    __tablename__ = "project_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="files")
    extractions: Mapped[list["ProjectDocumentExtraction"]] = relationship(
        back_populates="project_file",
        cascade="all, delete-orphan",
    )


class ProjectDigitalTwin(Base):
    """Representação digital unificada do projeto (Project Review Engine — Módulo A)."""

    __tablename__ = "project_digital_twin"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    disciplinas: Mapped[list | None] = mapped_column(JSON, nullable=True)
    elementos: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    documentos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    normas_aplicaveis: Mapped[list | None] = mapped_column(JSON, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="digital_twins")


class ProjectReview(Base):
    """Ciclo de revisão técnica de um projeto (Módulos G, L, S)."""

    __tablename__ = "project_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="recebido", index=True)
    scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parent_review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_reviews.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="reviews")
    parent_review: Mapped["ProjectReview | None"] = relationship(remote_side=[id])
    nonconformities: Mapped[list["ProjectNonconformity"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
    )


class ProjectNonconformity(Base):
    """Não conformidade registrada na revisão (Módulo H)."""

    __tablename__ = "project_nonconformities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_reviews.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True
    )
    codigo: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    categoria: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    criticidade: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    evidencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    norma: Mapped[str | None] = mapped_column(String(120), nullable=True)
    impacto: Mapped[str | None] = mapped_column(Text, nullable=True)
    recomendacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="aberta", index=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="nonconformities")
    review: Mapped["ProjectReview | None"] = relationship(back_populates="nonconformities")


class ProjectDocumentExtraction(Base):
    """Extração estruturada por arquivo (Módulos B, C, D, E, 0)."""

    __tablename__ = "project_document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discipline: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    format_key: Mapped[str] = mapped_column(String(20), nullable=False)
    extraction_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    vision_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project_file: Mapped["ProjectFile"] = relationship(back_populates="extractions")


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


class EvolutionSignalRecord(Base):
    """Evolution Loop v1 — sinais de execução coletados."""

    __tablename__ = "evolution_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    context_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    task_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    discipline: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    model_used: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rag_context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    output_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    signal_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvolutionMutation(Base):
    """Evolution Loop v1 — mutações propostas/aplicadas (audit trail)."""

    __tablename__ = "evolution_mutations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mutation_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    mutation_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    context_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    current_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proposed_value: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="proposed", index=True)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shadow_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentProposalRecord(Base):
    """Agent Generation Loop v1 — propostas de novos agentes (nunca auto-ativadas)."""

    __tablename__ = "agent_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    discipline: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    domain_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_improvement: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    dependencies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.35)
    baseline_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gap_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="proposed", index=True)
    evaluation_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    promotion_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    proposal_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AgentSimulationRecord(Base):
    """Agent Generation Loop v1 — execuções sandbox."""

    __tablename__ = "agent_simulations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_proposals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    proposal_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    discipline: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="heuristic")
    report_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BudgetDocument(Base):
    """Orçamento PPD persistido — sessão completa em JSON."""

    __tablename__ = "budget_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    grand_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    obra_type: Mapped[str] = mapped_column(String(8), nullable=False, default="RF")
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_summary(self) -> dict:
        return {
            "id": str(self.id),
            "title": self.title,
            "project_id": str(self.project_id) if self.project_id else None,
            "session_id": self.session_id,
            "grand_total": self.grand_total,
            "obra_type": self.obra_type,
            "input_text": self.input_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectActivityEvent(Base):
    """Timeline operacional por projeto — uploads, vision, orçamento, orquestração."""

    __tablename__ = "project_activity_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discipline: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phase: Mapped[str | None] = mapped_column(String(60), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    project: Mapped["Project | None"] = relationship(back_populates="activity_events")


class ProjectDecision(Base):
    """Memória de decisões técnicas/orçamentárias por projeto."""

    __tablename__ = "project_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    disciplines: Mapped[list | None] = mapped_column(JSON, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    project: Mapped["Project | None"] = relationship(back_populates="decisions")
