from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.schemas import HistoryResponse
from app.services import HistoryService
from core.auth.dependencies import get_current_user
from core.database import get_db
from core.database.models import User

router = APIRouter(prefix="/history", tags=["History"])
history_service = HistoryService()


@router.get("", response_model=HistoryResponse)
def history(
    limit: int = Query(default=50, ge=1, le=200),
    conversation_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """
    Histórico de conversas, logs do orchestrator e execuções de agentes.
    """
    return HistoryResponse(
        **history_service.list(
            limit=limit,
            conversation_id=conversation_id,
            db=db,
            user=user,
        )
    )
