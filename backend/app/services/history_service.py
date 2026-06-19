from typing import Optional

from sqlalchemy.orm import Session

from core.database.service import get_history


class HistoryService:
    """Consulta histórico persistido no PostgreSQL."""

    def list(
        self,
        limit: int = 50,
        conversation_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> dict:
        items = get_history(limit=limit, conversation_id=conversation_id, db=db)
        return {
            "total": len(items),
            "items": items,
        }
