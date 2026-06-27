from typing import Optional

from sqlalchemy.orm import Session

from core.database.conversation_access import conversation_user_id
from core.database.models import User
from core.database.service import get_history


class HistoryService:
    """Consulta histórico persistido no PostgreSQL."""

    def list(
        self,
        limit: int = 50,
        conversation_id: Optional[str] = None,
        db: Optional[Session] = None,
        user: Optional[User] = None,
    ) -> dict:
        items = get_history(
            limit=limit,
            conversation_id=conversation_id,
            user_id=conversation_user_id(user),
            db=db,
        )
        return {
            "total": len(items),
            "items": items,
        }
