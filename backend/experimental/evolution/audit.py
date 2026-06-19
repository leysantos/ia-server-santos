"""
Evolution Loop v1 — persistência auditável.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from experimental.evolution.signal_collector import EvolutionSignal

logger = logging.getLogger(__name__)


def save_execution_signal(signal: EvolutionSignal) -> Optional[dict[str, Any]]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return None
    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_evolution_signal(signal.to_dict())
            return repo.serialize_evolution_signal(row)
    except Exception as exc:
        logger.debug("Evolution signal persist falhou: %s", exc)
        return None


def save_evolution_mutation(entry: dict[str, Any]) -> Optional[dict[str, Any]]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return None
    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_evolution_mutation(entry)
            return repo.serialize_evolution_mutation(row)
    except Exception as exc:
        logger.debug("Evolution mutation persist falhou: %s", exc)
        return None


def list_recent_signals(
    context_key: Optional[str] = None,
    limit: int = 30,
) -> list[EvolutionSignal]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository
    from experimental.evolution.signal_collector import EvolutionSignal

    if not is_db_enabled():
        return []
    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            rows = repo.list_evolution_signals(context_key=context_key, limit=limit)
            return [
                EvolutionSignal(
                    source=r.source,
                    task_type=r.task_type,
                    discipline=r.discipline,
                    model_used=r.model_used,
                    prompt_version=r.prompt_version,
                    agent_name=r.agent_name,
                    rag_context_length=r.rag_context_length or 0,
                    input_hash=r.input_hash or "",
                    output_quality=r.output_quality,
                    latency_ms=r.latency_ms or 0.0,
                    success=r.success,
                )
                for r in rows
            ]
    except Exception:
        return []
