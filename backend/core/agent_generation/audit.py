"""
Agent Generation Loop v1 — persistência auditável (PostgreSQL).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def save_agent_proposal(proposal: dict[str, Any]) -> Optional[dict[str, Any]]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return None
    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_agent_proposal(proposal)
            return repo.serialize_agent_proposal(row)
    except Exception as exc:
        logger.debug("Agent proposal persist falhou: %s", exc)
        return None


def save_agent_simulation(simulation: dict[str, Any]) -> Optional[dict[str, Any]]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return None
    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_agent_simulation(simulation)
            return repo.serialize_agent_simulation(row)
    except Exception as exc:
        logger.debug("Agent simulation persist falhou: %s", exc)
        return None


def update_agent_proposal_status(
    proposal_id: str,
    status: str,
    *,
    evaluation: Optional[dict[str, Any]] = None,
    promotion: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return None
    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.update_agent_proposal_status(
                proposal_id,
                status,
                evaluation=evaluation,
                promotion=promotion,
            )
            return repo.serialize_agent_proposal(row) if row else None
    except Exception as exc:
        logger.debug("Agent proposal update falhou: %s", exc)
        return None
