from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.services.tech_spec_stream_service import TechSpecStreamService
from core.llm_override import llm_model_scope

from app.routes.pricing.schemas import TechSpecComposeRequest, TechSpecUpdateRequest
from app.routes.pricing.shared import _get_budget_engine

router = APIRouter()

@router.get("/budget/{session_id}/tech-spec")
def get_budget_tech_spec(session_id: str):
    engine = _get_budget_engine()
    try:
        spec = engine.get_tech_spec(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return {"tech_spec": spec}


@router.put("/budget/{session_id}/tech-spec")
def update_budget_tech_spec(session_id: str, body: TechSpecUpdateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.update_tech_spec(session_id, body.model_dump(exclude_none=True))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return {"tech_spec": session.tech_spec, "session": session.to_dict()}


@router.delete("/budget/{session_id}/tech-spec")
def clear_budget_tech_spec(session_id: str):
    engine = _get_budget_engine()
    try:
        session = engine.clear_tech_spec(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return {"tech_spec": None, "session": session.to_dict()}


@router.post("/budget/{session_id}/tech-spec/compose/stream")
def compose_budget_tech_spec_stream(session_id: str, body: TechSpecComposeRequest):
    service = TechSpecStreamService()
    with llm_model_scope(body.llm_model):
        return StreamingResponse(
            service.stream(
                session_id,
                body.prompt or "",
                mode="edit" if body.mode == "edit" else "generate",
                use_llm=body.use_llm,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream; charset=utf-8",
            },
        )


@router.get("/budget/{session_id}/tech-spec/export")
def export_budget_tech_spec(session_id: str):
    engine = _get_budget_engine()
    try:
        content = engine.export_tech_spec_docx(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="especificacao_tecnica_{session_id[:8]}.docx"'
        },
    )


@router.get("/budget/{session_id}/tech-spec/export/pdf")
def export_budget_tech_spec_pdf(session_id: str):
    engine = _get_budget_engine()
    try:
        content = engine.export_tech_spec_pdf(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="especificacao_tecnica_{session_id[:8]}.pdf"'
        },
    )
