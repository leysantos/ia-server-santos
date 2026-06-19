"""
Evaluation Logger — persistência fire-and-forget em copilot_evaluations.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from core.database.connection import is_db_enabled, session_scope
from core.database.repository import DatabaseRepository
from core.evaluation_v2.evaluation_engine import evaluate

logger = logging.getLogger(__name__)


def _parse_uuid(value: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def save_evaluation(evaluation: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Persiste avaliação no PostgreSQL. Retorna None se falhar."""
    if not is_db_enabled():
        logger.warning("Evaluation Loop v2: DB desabilitado — avaliação não salva")
        return None

    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_copilot_evaluation(
                input_text=evaluation.get("input") or "",
                intent=evaluation.get("intent"),
                conversation_id=_parse_uuid(evaluation.get("conversation_id")),
                intent_accuracy=evaluation.get("intent_accuracy", 0.0),
                plan_quality=evaluation.get("plan_quality", 0.0),
                execution_completeness=evaluation.get("execution_completeness", 0.0),
                response_quality=evaluation.get("response_quality", 0.0),
                final_score=evaluation.get("final_score", 0.0),
                issues=evaluation.get("issues"),
                scores_detail=evaluation.get("stages"),
            )
            return DatabaseRepository.serialize_copilot_evaluation(row)
    except Exception as exc:
        logger.warning("Evaluation Loop v2: falha ao salvar avaliação: %s", exc)
        return None


def run_evaluation_and_log(copilot_output: dict[str, Any]) -> dict[str, Any]:
    """
    Executa avaliação e tenta persistir (fire-and-forget safe).

    Falha de DB não propaga exceção — apenas log warning.
    """
    evaluation = evaluate(copilot_output)
    evaluation["saved"] = save_evaluation(evaluation) is not None
    return evaluation
