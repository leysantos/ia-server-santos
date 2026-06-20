"""Rotas REST — Project Review Engine (Módulo U)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.schemas.project_review import (
    CompareVersionsResponse,
    DashboardResponse,
    DigitalTwinResponse,
    ExtractionListResponse,
    NCListResponse,
    NCSummary,
    NCStatusUpdate,
    ReviewDetail,
    ReviewListResponse,
    ReviewStartRequest,
    ReviewStatusUpdate,
    ReviewSummary,
)
from app.services.project_review_service import ProjectReviewService
from core.database import get_db

router = APIRouter(prefix="/projects", tags=["Project Review"])
service = ProjectReviewService()


@router.get("/{project_id}/review/dashboard", response_model=DashboardResponse)
def review_dashboard(project_id: str, db: Session = Depends(get_db)):
    return DashboardResponse(**service.dashboard(project_id, db))


@router.get("/review/dashboard", response_model=DashboardResponse)
def review_dashboard_global(db: Session = Depends(get_db)):
    return DashboardResponse(**service.dashboard(None, db))


@router.get("/{project_id}/review", response_model=ReviewListResponse)
def list_reviews(project_id: str, db: Session = Depends(get_db)):
    data = service.list_reviews(project_id, db)
    return ReviewListResponse(
        total=data["total"],
        items=[ReviewSummary(**item) for item in data["items"]],
    )


@router.post("/{project_id}/review/start", response_model=ReviewDetail)
def start_review(
    project_id: str,
    body: ReviewStartRequest,
    db: Session = Depends(get_db),
):
    return ReviewDetail(**service.start_review(
        project_id,
        parent_review_id=body.parent_review_id,
        enable_vision=body.enable_vision,
        db=db,
    ))


@router.get("/{project_id}/review/{review_id}", response_model=ReviewDetail)
def get_review(project_id: str, review_id: str, db: Session = Depends(get_db)):
    return ReviewDetail(**service.get_review(project_id, review_id, db))


@router.patch("/{project_id}/review/{review_id}/status", response_model=ReviewDetail)
def update_review_status(
    project_id: str,
    review_id: str,
    body: ReviewStatusUpdate,
    db: Session = Depends(get_db),
):
    return ReviewDetail(**service.update_review_status(project_id, review_id, body.status, db))


@router.get("/{project_id}/review/{review_id}/ncs", response_model=NCListResponse)
def list_review_ncs(project_id: str, review_id: str, db: Session = Depends(get_db)):
    data = service.list_ncs(project_id, review_id, db)
    return NCListResponse(total=data["total"], items=[NCSummary(**i) for i in data["items"]])


@router.get("/{project_id}/ncs", response_model=NCListResponse)
def list_project_ncs(
    project_id: str,
    review_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    data = service.list_ncs(project_id, review_id, db)
    return NCListResponse(total=data["total"], items=[NCSummary(**i) for i in data["items"]])


@router.patch("/{project_id}/ncs/{nc_id}", response_model=NCSummary)
def update_nc_status(
    project_id: str,
    nc_id: str,
    body: NCStatusUpdate,
    db: Session = Depends(get_db),
):
    return NCSummary(**service.update_nc_status(project_id, nc_id, body.status, db))


@router.get("/{project_id}/digital-twin", response_model=DigitalTwinResponse)
def get_digital_twin(project_id: str, db: Session = Depends(get_db)):
    return DigitalTwinResponse(**service.get_digital_twin(project_id, db))


@router.get("/{project_id}/extractions", response_model=ExtractionListResponse)
def list_extractions(project_id: str, db: Session = Depends(get_db)):
    return ExtractionListResponse(**service.list_extractions(project_id, db))


@router.get("/{project_id}/review/compare", response_model=CompareVersionsResponse)
def compare_reviews(
    project_id: str,
    v1: str = Query(..., description="ID revisão V1"),
    v2: str = Query(..., description="ID revisão V2"),
    db: Session = Depends(get_db),
):
    return CompareVersionsResponse(**service.compare_versions(project_id, v1, v2, db))


@router.get("/{project_id}/review/{review_id}/export/{report_type}")
def export_report(
    project_id: str,
    review_id: str,
    report_type: str,
    db: Session = Depends(get_db),
):
    content, filename = service.export_report(project_id, review_id, report_type, db)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
