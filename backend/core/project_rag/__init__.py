"""Resolve project_id a partir da conversa ou parâmetro explícito."""

from __future__ import annotations

from typing import Optional

from core.database.service import get_conversation_detail


def resolve_project_id(
    conversation_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Optional[str]:
    if project_id:
        return project_id
    if not conversation_id:
        return None
    conv = get_conversation_detail(conversation_id)
    if conv and conv.get("project_id"):
        return str(conv["project_id"])
    return None
