from typing import Optional

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.activity import (
    ConsoleLiveResponse,
    ConsoleLogsResponse,
    ConsoleStatsResponse,
    OllamaQueueSnapshot,
    OllamaRunningModel,
    OpsLogItem,
    RuntimeJobItem,
    UnloadModelRequest,
    UnloadResponse,
    VramSnapshot,
)
from core.database import get_db
from core.project_memory.service import console_stats, list_console_logs
from core.runtime.job_registry import get_job_registry
from core.runtime.live_snapshot import build_live_snapshot
from core.runtime.ollama_runtime import unload_all_models, unload_model
from core.stream_events import format_sse, format_sse_keepalive

router = APIRouter(prefix="/console", tags=["Console"])


def _map_live(data: dict) -> ConsoleLiveResponse:
    ollama = data.get("ollama") or {}
    queue_raw = data.get("ollama_queue")
    queue = OllamaQueueSnapshot(**queue_raw) if queue_raw else None
    vram_raw = data.get("vram")
    vram = VramSnapshot(**vram_raw) if vram_raw else None
    return ConsoleLiveResponse(
        timestamp=data.get("timestamp"),
        ollama_reachable=bool(ollama.get("reachable")),
        ollama_error=ollama.get("error"),
        loaded_models=[OllamaRunningModel(**m) for m in ollama.get("models") or []],
        gpu=data.get("gpu"),
        cpu_percent=data.get("cpu_percent"),
        memory_percent=data.get("memory_percent"),
        active_jobs=[RuntimeJobItem(**j) for j in data.get("active_jobs") or []],
        recent_jobs=[RuntimeJobItem(**j) for j in data.get("recent_jobs") or []],
        active_job_count=data.get("active_job_count", 0),
        loaded_model_count=data.get("loaded_model_count", 0),
        ollama_queue=queue,
        ops_logs=[OpsLogItem(**row) for row in data.get("ops_logs") or []],
        vram=vram,
    )


@router.get("/live", response_model=ConsoleLiveResponse)
def get_console_live():
    """Snapshot em tempo real: GPU, modelos Ollama carregados e jobs ativos."""
    try:
        return _map_live(build_live_snapshot())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/live/stream")
def console_live_stream(
    interval_ms: float = Query(default=1500, ge=500, le=10000),
):
    """SSE com snapshot live do console (~1,5s por tick)."""

    def event_stream():
        yield format_sse("status", {"message": "Console SSE conectado", "phase": "connected"})
        while True:
            try:
                payload = _map_live(build_live_snapshot()).model_dump()
                yield format_sse("live", payload)
            except Exception as exc:
                yield format_sse("error", {"message": str(exc), "phase": "error"})
            yield format_sse_keepalive()
            time.sleep(interval_ms / 1000.0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.get("/logs", response_model=ConsoleLogsResponse)
def get_console_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Logs recentes do orchestrator com execuções de agentes (read-only)."""
    try:
        items = list_console_logs(db, limit=limit)
        return ConsoleLogsResponse(total=len(items), items=items)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc


@router.get("/stats", response_model=ConsoleStatsResponse)
def get_console_stats(db: Session = Depends(get_db)):
    """Contadores agregados para o Orchestrator Console."""
    try:
        return ConsoleStatsResponse(**console_stats(db))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Solicita cancelamento cooperativo de um job longo (ex.: visão entre arquivos)."""
    registry = get_job_registry()
    if not registry.request_cancel(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado ou já encerrado")
    return {"ok": True, "job_id": job_id, "message": "Cancelamento solicitado"}


@router.post("/ollama/unload", response_model=UnloadResponse)
def ollama_unload_model(body: UnloadModelRequest):
    """Descarrega um modelo da VRAM (interrompe inferência em curso neste modelo)."""
    result = unload_model(body.model)
    if not result.get("ok"):
        return UnloadResponse(ok=False, error=result.get("error"))
    return UnloadResponse(ok=True, unloaded=[body.model])


@router.post("/ollama/unload-all", response_model=UnloadResponse)
def ollama_unload_all():
    """Descarrega todos os modelos residentes no Ollama."""
    result = unload_all_models()
    return UnloadResponse(
        ok=bool(result.get("ok")),
        unloaded=result.get("unloaded") or [],
        errors=result.get("errors") or [],
        error=result.get("error"),
    )
