"""Persistência auditável de execuções AED v1."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from core.database.connection import is_db_enabled, session_scope
from core.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)


def save_aed_run(output: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not is_db_enabled():
        return None

    try:
        conv_id = None
        raw = output.get("conversation_id")
        if raw:
            conv_id = uuid.UUID(str(raw))

        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_aed_run(
                input_text=output.get("input", ""),
                understanding=output.get("understanding"),
                designs=output.get("designs"),
                simulations=output.get("simulations"),
                comparison=output.get("comparison"),
                selection=output.get("selection"),
                report=output.get("report"),
                conversation_id=conv_id,
            )
            return DatabaseRepository.serialize_aed_run(row)
    except Exception as exc:
        logger.warning("AED: falha ao salvar run: %s", exc)
        return None
