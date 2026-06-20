"""Schemas REST — Project Review Engine."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ReviewStartRequest(BaseModel):
    parent_review_id: Optional[str] = None
    enable_vision: bool = True


class ReviewStatusUpdate(BaseModel):
    status: str = Field(..., description="Novo status do workflow")


class NCStatusUpdate(BaseModel):
    status: str


class ReviewSummary(BaseModel):
    id: str
    project_id: str
    version: int
    status: str
    scores: Optional[dict[str, float]] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None


class ReviewDetail(ReviewSummary):
    analysis_payload: Optional[dict[str, Any]] = None
    report_payload: Optional[dict[str, Any]] = None
    parent_review_id: Optional[str] = None


class ReviewListResponse(BaseModel):
    total: int
    items: list[ReviewSummary]


class NCSummary(BaseModel):
    id: str
    project_id: str
    review_id: Optional[str] = None
    codigo: str
    categoria: str
    criticidade: str
    descricao: str
    evidencia: Optional[str] = None
    norma: Optional[str] = None
    impacto: Optional[str] = None
    recomendacao: Optional[str] = None
    status: str


class NCListResponse(BaseModel):
    total: int
    items: list[NCSummary]


class DigitalTwinResponse(BaseModel):
    id: str
    project_id: str
    disciplinas: Optional[list[str]] = None
    elementos: Optional[dict[str, Any]] = None
    documentos: Optional[list[Any]] = None
    normas_aplicaveis: Optional[list[str]] = None
    payload: Optional[dict[str, Any]] = None
    versao: int
    created_at: Optional[str] = None


class ExtractionSummary(BaseModel):
    id: str
    project_file_id: str
    discipline: Optional[str] = None
    format_key: str
    processed_at: Optional[str] = None


class ExtractionListResponse(BaseModel):
    total: int
    items: list[ExtractionSummary]


class DashboardResponse(BaseModel):
    project_id: Optional[str] = None
    reviews_total: int
    ncs_total: int
    latest_review: Optional[ReviewSummary] = None
    scores: Optional[dict[str, float]] = None
    pending_ncs: int = 0


class CompareVersionsResponse(BaseModel):
    v1_review_id: str
    v2_review_id: str
    comparison: dict[str, list[dict[str, Any]]]
