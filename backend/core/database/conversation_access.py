"""Controle de acesso a conversas por usuário."""

from __future__ import annotations

import uuid

from core.database.models import Conversation, User


def conversation_user_id(user: User | None) -> uuid.UUID | None:
    """UUID do dono quando auth ativo; None quando auth desligado (modo legado)."""
    return user.id if user else None


def user_owns_conversation(
    conversation: Conversation | None,
    user_id: uuid.UUID | None,
) -> bool:
    if conversation is None:
        return False
    if user_id is None:
        return True
    return conversation.user_id == user_id
