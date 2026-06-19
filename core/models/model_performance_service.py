"""
Persistência e auto-learning do Model Evaluation Loop v1.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.models.model_evaluation_loop import RECALIBRATE_EVERY

logger = logging.getLogger(__name__)


def save_model_evaluation(**kwargs: Any) -> Optional[dict[str, Any]]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return None

    with session_scope() as session:
        repo = DatabaseRepository(session)
        row = repo.create_model_evaluation(**kwargs)
        return repo.serialize_model_evaluation(row)


def get_best_model_from_profile(
    task_type: str,
    discipline: Optional[str] = None,
) -> Optional[str]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return None

    with session_scope() as session:
        repo = DatabaseRepository(session)
        profile = repo.get_best_performance_profile(task_type, discipline or "GERAL")
        if profile:
            return profile.model_name
    return None


def list_performance_profiles(
    task_type: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return []

    with session_scope() as session:
        repo = DatabaseRepository(session)
        rows = repo.list_model_performance_profiles(task_type=task_type, limit=limit)
        return [repo.serialize_model_performance_profile(r) for r in rows]


def maybe_recalibrate_profiles(task_type: str, discipline: str) -> None:
    """A cada RECALIBRATE_EVERY avaliações por task+disciplina, recalcula ranking."""
    from core.database.connection import is_db_enabled, session_scope
    from core.database.repository import DatabaseRepository

    if not is_db_enabled():
        return

    with session_scope() as session:
        repo = DatabaseRepository(session)
        count = repo.count_model_evaluations(task_type, discipline)
        if count == 0 or count % RECALIBRATE_EVERY != 0:
            return

        repo.rebuild_performance_profiles(task_type, discipline)
        best = repo.get_best_performance_profile(task_type, discipline)

    if best:
        from core.models.model_router import get_model_router

        router = get_model_router()
        router.apply_learned_model(task_type, best.model_name)
        logger.info(
            "model_evaluation recalibrated task=%s discipline=%s best_model=%s win_rate=%.3f n=%d",
            task_type,
            discipline,
            best.model_name,
            best.win_rate,
            best.total_evaluations,
        )
