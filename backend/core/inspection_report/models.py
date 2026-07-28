"""Modelos SQLAlchemy — laudos de vistoria."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models import Base


class InspectionReportTemplate(Base):
    __tablename__ = "inspection_report_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discipline_hint: Mapped[str] = mapped_column(String(60), nullable=False, default="GERAL")
    chapters: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reports: Mapped[list["InspectionReport"]] = relationship(back_populates="template")


class InspectionReport(Base):
    __tablename__ = "inspection_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="Laudo de vistoria")
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspection_report_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="draft", index=True
    )
    # attachments | attachments_and_kb
    knowledge_mode: Mapped[str] = mapped_column(
        String(40), nullable=False, default="attachments_and_kb"
    )
    # Quando True, a geração sugere ensaios instrumentados conforme tipología + gravidade
    suggest_instrumented_tests: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correction_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    gemini_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
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

    template: Mapped[InspectionReportTemplate | None] = relationship(back_populates="reports")
    assets: Mapped[list["InspectionReportAsset"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class InspectionReportAsset(Base):
    __tablename__ = "inspection_report_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspection_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # document | image | norm
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="document")
    filename: Mapped[str] = mapped_column(String(260), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(20), nullable=True)  # landscape|portrait
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped[InspectionReport] = relationship(back_populates="assets")
