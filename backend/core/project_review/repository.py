"""Repositório PostgreSQL — Project Review Engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from core.database.models import (
    Project,
    ProjectDigitalTwin,
    ProjectDocumentExtraction,
    ProjectNonconformity,
    ProjectReview,
)


class ProjectReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_project(self, project_id: uuid.UUID) -> Project | None:
        return self.db.get(Project, project_id)

    def list_reviews(self, project_id: uuid.UUID, limit: int = 20) -> list[ProjectReview]:
        stmt = (
            select(ProjectReview)
            .where(ProjectReview.project_id == project_id)
            .order_by(desc(ProjectReview.version))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_review(self, review_id: uuid.UUID) -> ProjectReview | None:
        return self.db.get(ProjectReview, review_id)

    def latest_review(self, project_id: uuid.UUID) -> ProjectReview | None:
        stmt = (
            select(ProjectReview)
            .where(ProjectReview.project_id == project_id)
            .order_by(desc(ProjectReview.version))
            .limit(1)
        )
        return self.db.scalar(stmt)

    def next_review_version(self, project_id: uuid.UUID) -> int:
        stmt = select(func.max(ProjectReview.version)).where(ProjectReview.project_id == project_id)
        current = self.db.scalar(stmt)
        return (current or 0) + 1

    def create_review(
        self,
        project_id: uuid.UUID,
        *,
        parent_review_id: uuid.UUID | None = None,
        status: str = "recebido",
    ) -> ProjectReview:
        review = ProjectReview(
            project_id=project_id,
            version=self.next_review_version(project_id),
            status=status,
            parent_review_id=parent_review_id,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(review)
        self.db.flush()
        return review

    def update_review(self, review: ProjectReview, **fields: Any) -> ProjectReview:
        for key, value in fields.items():
            if hasattr(review, key):
                setattr(review, key, value)
        self.db.flush()
        return review

    def save_extraction(
        self,
        *,
        project_id: uuid.UUID,
        project_file_id: uuid.UUID,
        discipline: str | None,
        format_key: str,
        extraction_json: dict | None,
        vision_json: dict | None,
    ) -> ProjectDocumentExtraction:
        stmt = select(ProjectDocumentExtraction).where(
            ProjectDocumentExtraction.project_file_id == project_file_id
        )
        existing = self.db.scalar(stmt)
        if existing:
            existing.discipline = discipline
            existing.format_key = format_key
            existing.extraction_json = extraction_json
            existing.vision_json = vision_json
            existing.processed_at = datetime.now(timezone.utc)
            self.db.flush()
            return existing

        row = ProjectDocumentExtraction(
            project_id=project_id,
            project_file_id=project_file_id,
            discipline=discipline,
            format_key=format_key,
            extraction_json=extraction_json,
            vision_json=vision_json,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_extractions(self, project_id: uuid.UUID) -> list[ProjectDocumentExtraction]:
        stmt = (
            select(ProjectDocumentExtraction)
            .where(ProjectDocumentExtraction.project_id == project_id)
            .order_by(desc(ProjectDocumentExtraction.processed_at))
        )
        return list(self.db.scalars(stmt).all())

    def save_digital_twin(
        self,
        project_id: uuid.UUID,
        snapshot: dict[str, Any],
    ) -> ProjectDigitalTwin:
        twin = ProjectDigitalTwin(
            project_id=project_id,
            disciplinas=snapshot.get("disciplinas"),
            elementos=snapshot.get("elementos"),
            documentos=snapshot.get("documentos"),
            normas_aplicaveis=snapshot.get("normas_aplicaveis"),
            payload=snapshot.get("payload"),
            versao=snapshot.get("versao", 1),
        )
        self.db.add(twin)
        self.db.flush()
        return twin

    def latest_digital_twin(self, project_id: uuid.UUID) -> ProjectDigitalTwin | None:
        stmt = (
            select(ProjectDigitalTwin)
            .where(ProjectDigitalTwin.project_id == project_id)
            .order_by(desc(ProjectDigitalTwin.versao))
            .limit(1)
        )
        return self.db.scalar(stmt)

    def bulk_create_ncs(self, ncs: list[dict[str, Any]]) -> list[ProjectNonconformity]:
        rows: list[ProjectNonconformity] = []
        for data in ncs:
            row = ProjectNonconformity(
                project_id=data["project_id"],
                review_id=data.get("review_id"),
                project_file_id=data.get("project_file_id"),
                codigo=data["codigo"],
                categoria=data["categoria"],
                criticidade=data["criticidade"],
                descricao=data["descricao"],
                evidencia=data.get("evidencia"),
                norma=data.get("norma"),
                impacto=data.get("impacto"),
                recomendacao=data.get("recomendacao"),
                status=data.get("status", "aberta"),
                extra=data.get("extra"),
            )
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return rows

    def list_ncs(
        self,
        project_id: uuid.UUID,
        *,
        review_id: uuid.UUID | None = None,
        limit: int = 200,
    ) -> list[ProjectNonconformity]:
        stmt = select(ProjectNonconformity).where(ProjectNonconformity.project_id == project_id)
        if review_id:
            stmt = stmt.where(ProjectNonconformity.review_id == review_id)
        stmt = stmt.order_by(desc(ProjectNonconformity.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())

    def dashboard_stats(self, project_id: Optional[uuid.UUID] = None) -> dict[str, Any]:
        review_q = select(func.count(ProjectReview.id))
        nc_q = select(func.count(ProjectNonconformity.id))
        if project_id:
            review_q = review_q.where(ProjectReview.project_id == project_id)
            nc_q = nc_q.where(ProjectNonconformity.project_id == project_id)
        return {
            "reviews_total": self.db.scalar(review_q) or 0,
            "ncs_total": self.db.scalar(nc_q) or 0,
        }

    @staticmethod
    def review_to_dict(review: ProjectReview) -> dict[str, Any]:
        return {
            "id": str(review.id),
            "project_id": str(review.project_id),
            "version": review.version,
            "status": review.status,
            "scores": review.scores,
            "analysis_payload": review.analysis_payload,
            "report_payload": review.report_payload,
            "parent_review_id": str(review.parent_review_id) if review.parent_review_id else None,
            "started_at": review.started_at.isoformat() if review.started_at else None,
            "completed_at": review.completed_at.isoformat() if review.completed_at else None,
            "created_at": review.created_at.isoformat() if review.created_at else None,
        }

    @staticmethod
    def nc_to_dict(nc: ProjectNonconformity) -> dict[str, Any]:
        return {
            "id": str(nc.id),
            "project_id": str(nc.project_id),
            "review_id": str(nc.review_id) if nc.review_id else None,
            "codigo": nc.codigo,
            "categoria": nc.categoria,
            "criticidade": nc.criticidade,
            "descricao": nc.descricao,
            "evidencia": nc.evidencia,
            "norma": nc.norma,
            "impacto": nc.impacto,
            "recomendacao": nc.recomendacao,
            "status": nc.status,
        }

    @staticmethod
    def twin_to_dict(twin: ProjectDigitalTwin) -> dict[str, Any]:
        return {
            "id": str(twin.id),
            "project_id": str(twin.project_id),
            "disciplinas": twin.disciplinas,
            "elementos": twin.elementos,
            "documentos": twin.documentos,
            "normas_aplicaveis": twin.normas_aplicaveis,
            "payload": twin.payload,
            "versao": twin.versao,
            "created_at": twin.created_at.isoformat() if twin.created_at else None,
        }
