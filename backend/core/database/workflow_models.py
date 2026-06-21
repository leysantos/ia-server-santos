"""Entidades do módulo Workflow Projetos — multi-tenant, pranchas, revisões, eventos."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="empresa")
    templates: Mapped[list["CompanyTemplate"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    stamps: Mapped[list["CompanyStamp"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    settings: Mapped[list["CompanySetting"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    signatures: Mapped[list["CompanySignature"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    sheet_templates: Mapped[list["WorkflowTemplate"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class CompanyTemplate(Base):
    __tablename__ = "company_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    formato: Mapped[str] = mapped_column(String(10), nullable=False)
    orientacao: Mapped[str] = mapped_column(String(20), nullable=False, default="retrato")
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="templates")


class CompanyStamp(Base):
    __tablename__ = "company_stamps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    posicao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="stamps")


class CompanySetting(Base):
    __tablename__ = "company_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chave: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    valor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="settings")


class CompanySignature(Base):
    __tablename__ = "company_signatures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rotulo: Mapped[str] = mapped_column(String(120), nullable=False)
    cert_type: Mapped[str] = mapped_column(String(20), nullable=False, default="A1")
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="signatures")


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    project: Mapped["Project | None"] = relationship(back_populates="workflow_events")


class ProjectFolder(Base):
    __tablename__ = "project_folders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_folders.id", ondelete="CASCADE"), nullable=True, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    disciplina: Mapped[str | None] = mapped_column(String(60), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="workflow_folders")
    parent: Mapped["ProjectFolder | None"] = relationship(remote_side=[id])


class WorkflowDrawing(Base):
    __tablename__ = "workflow_drawings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True, index=True
    )
    classificacao: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    escala: Mapped[str | None] = mapped_column(String(20), nullable=True)
    disciplina: Mapped[str | None] = mapped_column(String(60), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="workflow_drawings")


class WorkflowSheet(Base):
    __tablename__ = "workflow_sheets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_templates.id", ondelete="SET NULL"), nullable=True
    )
    numero_prancha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    codigo_desenho: Mapped[str | None] = mapped_column(String(80), nullable=True)
    escala: Mapped[str | None] = mapped_column(String(20), nullable=True)
    disciplina: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="rascunho")
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    layout_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="workflow_sheets")


class WorkflowRevision(Base):
    __tablename__ = "workflow_revisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    autor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    arquivo_origem_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True
    )
    arquivo_destino_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="workflow_revisions")


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch: Mapped[str] = mapped_column(String(80), nullable=False, default="main", index=True)
    tag: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    commit_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_versions.id", ondelete="SET NULL"), nullable=True
    )
    mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="workflow_versions")
    parent: Mapped["WorkflowVersion | None"] = relationship(remote_side=[id])


class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    formato: Mapped[str] = mapped_column(String(10), nullable=False)
    orientacao: Mapped[str] = mapped_column(String(20), nullable=False, default="retrato")
    disciplina: Mapped[str | None] = mapped_column(String(60), nullable=True)
    placeholders: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company | None"] = relationship(back_populates="sheet_templates")


class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowDelivery(Base):
    __tablename__ = "workflow_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_revisions.id", ondelete="SET NULL"), nullable=True
    )
    package_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pendente")
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="workflow_deliveries")


class WorkflowDeliveryPackage(Base):
    """Sessão do wizard de entrega — pacote GRD profissional."""

    __tablename__ = "workflow_delivery_packages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    codigo_emissao: Mapped[str] = mapped_column(String(20), nullable=False, default="REV01")
    formato_padrao: Mapped[str] = mapped_column(String(10), nullable=False, default="A1")
    orientacao_padrao: Mapped[str] = mapped_column(String(20), nullable=False, default="paisagem")
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_templates.id", ondelete="SET NULL"), nullable=True
    )
    stamp_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_stamps.id", ondelete="SET NULL"), nullable=True
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    structure_preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    package_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_delivery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_deliveries.id", ondelete="SET NULL"), nullable=True
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
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="workflow_delivery_packages")
    items: Mapped[list["WorkflowPackageItem"]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="WorkflowPackageItem.sort_order",
    )


class WorkflowPackageItem(Base):
    """Item selecionado no pacote de entrega."""

    __tablename__ = "workflow_package_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_delivery_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="documento")
    disciplina: Mapped[str | None] = mapped_column(String(60), nullable=True)
    disciplina_codigo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    folha_numero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tipo_desenho: Mapped[str | None] = mapped_column(String(40), nullable=True)
    titulo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    codigo_sugerido: Mapped[str | None] = mapped_column(String(120), nullable=True)
    codigo_aprovado: Mapped[str | None] = mapped_column(String(120), nullable=True)
    arquivo_final: Mapped[str | None] = mapped_column(String(200), nullable=True)
    formato: Mapped[str | None] = mapped_column(String(10), nullable=True)
    escala: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pasta_destino: Mapped[str | None] = mapped_column(String(120), nullable=True)
    revisao_documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    package: Mapped["WorkflowDeliveryPackage"] = relationship(back_populates="items")
    project_file: Mapped["ProjectFile"] = relationship()
