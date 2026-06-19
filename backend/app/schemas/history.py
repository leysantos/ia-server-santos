from typing import Any, Optional

from pydantic import BaseModel, Field


class HistoryResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


class HistoryQuery(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    conversation_id: Optional[str] = None
