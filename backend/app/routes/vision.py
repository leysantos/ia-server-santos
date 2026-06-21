"""Rotas REST — Vision Analysis Engine (Gemma3 + Qwen3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.vision import (
    VisionAnalysisListResponse,
    VisionAnalyzeRequest,
    VisionAnalyzeResponse,
    VisionAnalysisItem,
    VisionModeItem,
    VisionReportRequest,
    VisionStatusResponse,
    VisionWorkspaceStatusResponse,
    WorkspaceReportItem,
    WorkspaceToolItem,
    PciChecklistResponse,
)
from app.services.vision_service import VisionService
from core.database import get_db

router = APIRouter(prefix="/projects", tags=["Vision Analysis"])
service = VisionService()


@router.get("/vision/status", response_model=VisionStatusResponse)
def vision_status():
    """Verifica Ollama + gemma3:12b (visão) e qwen3:14b (relatório)."""
    data = service.get_status()
    return VisionStatusResponse(
        available=data.get("available", False),
        ollama_reachable=data.get("ollama_reachable", False),
        vision_models_ready=data.get("vision_models_ready", []),
        primary=data.get("primary", ""),
        technical_model=data.get("technical_model", "qwen3:14b"),
        error=data.get("error"),
    )


@router.get("/vision/workspace-status", response_model=VisionWorkspaceStatusResponse)
def vision_workspace_status():
    """Checklist completo: analisadores, relatórios, deps e rotas do workspace."""
    data = service.get_workspace_status()
    return VisionWorkspaceStatusResponse(
        ready=data.get("ready", False),
        ollama_reachable=data.get("ollama_reachable", False),
        vision_model=data.get("vision_model", ""),
        vision_model_ready=data.get("vision_model_ready", False),
        technical_model=data.get("technical_model", ""),
        technical_model_ready=data.get("technical_model_ready", False),
        installed_models=data.get("installed_models", []),
        analyzers=[WorkspaceToolItem(**a) for a in data.get("analyzers", [])],
        reports=[WorkspaceReportItem(**r) for r in data.get("reports", [])],
        dependencies=data.get("dependencies", {}),
        pipeline=data.get("pipeline", []),
        frontend_routes=data.get("frontend_routes", []),
    )


@router.get("/vision/modes")
def vision_modes():
    return {"modes": [VisionModeItem(**m) for m in service.vision.list_modes()]}


@router.get("/{project_id}/vision/analyses", response_model=VisionAnalysisListResponse)
def list_vision_analyses(project_id: str, db: Session = Depends(get_db)):
    data = service.list_analyses(project_id, db)
    return VisionAnalysisListResponse(
        total=data["total"],
        items=[VisionAnalysisItem(**item) for item in data["items"]],
    )


@router.get("/{project_id}/vision/pci-checklist", response_model=PciChecklistResponse)
def pci_checklist(project_id: str, db: Session = Depends(get_db)):
    """Checklist IT-11 / NT-03 / PSCIP cruzando análises visuais do projeto."""
    return PciChecklistResponse(**service.get_pci_checklist(project_id, db))


@router.post("/{project_id}/vision/analyze", response_model=VisionAnalyzeResponse)
def analyze_vision(
    project_id: str,
    body: VisionAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """Pipeline: OCR → Gemma3 Vision → JSON → Qwen3 Relatório Técnico."""
    data = service.analyze(
        project_id,
        file_ids=body.file_ids,
        mode=body.mode,
        extra_context=body.extra_context,
        skip_technical=body.skip_technical,
        db=db,
    )
    return VisionAnalyzeResponse(
        project_id=data["project_id"],
        mode=data["mode"],
        total=data["total"],
        analyzed=data["analyzed"],
        errors=data["errors"],
        skipped=data["skipped"],
        items=[VisionAnalysisItem(**item) for item in data["items"]],
        summary=data.get("summary", {}),
        pci_checklist=PciChecklistResponse(**data["pci_checklist"])
        if data.get("pci_checklist")
        else None,
    )


@router.post("/{project_id}/vision/analyze/stream")
def analyze_vision_stream(
    project_id: str,
    body: VisionAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """Análise visual com progresso SSE (lotes grandes de fotos)."""
    from core.runtime.job_registry import get_job_registry

    service.list_analyses(project_id, db)
    registry = get_job_registry()
    job = registry.register(
        kind="vision",
        label=f"Análise visual ({body.mode})"
        + (" · rápida" if body.skip_technical else ""),
        project_id=project_id,
        meta={"mode": body.mode, "skip_technical": body.skip_technical},
    )

    def event_stream():
        try:
            for chunk in service.analyze_stream_events(
                project_id,
                file_ids=body.file_ids,
                mode=body.mode,
                extra_context=body.extra_context,
                skip_technical=body.skip_technical,
                job_id=job.id,
            ):
                yield chunk
        except Exception as exc:
            from core.stream_events import format_sse

            registry.finish(job.id, status="error", message=str(exc))
            yield format_sse("error", {"error": str(exc), "job_id": job.id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/{project_id}/vision/report")
def export_vision_report(
    project_id: str,
    body: VisionReportRequest,
    db: Session = Depends(get_db),
):
    """Exporta relatórios DOCX (visão + revisão técnica)."""
    content, filename = service.export_report(
        project_id,
        report_type=body.report_type,
        file_ids=body.file_ids,
        obra_info=body.obra_info,
        solicitante=body.solicitante,
        objeto=body.objeto,
        discipline=body.discipline,
        prazo=body.prazo,
        db=db,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
