from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.activity import ConsoleLogsResponse, ConsoleStatsResponse
from core.database import get_db
from core.project_memory.service import console_stats, list_console_logs

router = APIRouter(prefix="/console", tags=["Console"])


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
