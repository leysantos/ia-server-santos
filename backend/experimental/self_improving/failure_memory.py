"""
Failure Memory — persistência de falhas detectadas (PostgreSQL).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from core.database.connection import is_db_enabled, session_scope
from core.database.repository import DatabaseRepository

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


def record_failure(
    *,
    input_text: str,
    failure_type: str,
    route_decision: Optional[dict[str, Any]] = None,
    agent_used: Optional[str] = None,
    evaluation_scores: Optional[dict[str, Any]] = None,
    suggested_fix: Optional[str] = None,
    conversation_id: Optional[str | uuid.UUID] = None,
) -> Optional[dict[str, Any]]:
    """Registra falha no PostgreSQL. Fire-and-forget safe."""
    if not is_db_enabled():
        return None

    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_system_failure(
                input_text=input_text,
                failure_type=failure_type,
                route_decision=route_decision,
                agent_used=agent_used,
                evaluation_scores=evaluation_scores,
                suggested_fix=suggested_fix,
                conversation_id=_parse_uuid(conversation_id),
            )
            return DatabaseRepository.serialize_system_failure(row)
    except Exception as exc:
        logger.warning("Self-Improving Loop: falha ao registrar system_failure: %s", exc)
        return None


def list_recent_failures(
    limit: int = 100,
    failure_type: Optional[str] = None,
    discipline: Optional[str] = None,
) -> list[dict[str, Any]]:
    if not is_db_enabled():
        return []

    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            rows = repo.list_system_failures(
                limit=limit,
                failure_type=failure_type,
            )
            results = [DatabaseRepository.serialize_system_failure(r) for r in rows]
            if discipline:
                results = [
                    r for r in results
                    if discipline in (r.get("route_decision") or {}).get("disciplines", [])
                    or (r.get("route_decision") or {}).get("discipline") == discipline
                ]
            return results
    except Exception as exc:
        logger.warning("Self-Improving Loop: falha ao listar failures: %s", exc)
        return []


def count_failures_by_type(limit: int = 500) -> dict[str, int]:
    failures = list_recent_failures(limit=limit)
    counts: dict[str, int] = {}
    for f in failures:
        ft = f.get("failure_type") or "unknown"
        counts[ft] = counts.get(ft, 0) + 1
    return counts


def count_failures_by_discipline(limit: int = 500) -> dict[str, int]:
    failures = list_recent_failures(limit=limit)
    counts: dict[str, int] = {}
    for f in failures:
        route = f.get("route_decision") or {}
        for disc in route.get("disciplines") or [route.get("discipline")]:
            if disc:
                counts[disc] = counts.get(disc, 0) + 1
    return counts


def save_patch_proposal(patch: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Persiste proposta de patch versionada. Fire-and-forget safe."""
    if not is_db_enabled():
        return None

    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            row = repo.create_system_patch(
                patch_key=patch.get("patch_key", "unknown"),
                patch_version=int(patch.get("patch_version", 1)),
                patch_type=patch.get("patch_type", "generic"),
                content=patch,
                status=patch.get("status", "proposed"),
                risk_score=float(patch.get("risk_score", 0.0)),
                impact_score=float(patch.get("impact_score", 0.0)),
                source_finding=patch.get("source_finding"),
            )
            return DatabaseRepository.serialize_system_patch(row)
    except Exception as exc:
        logger.warning("Self-Improving Loop: falha ao salvar patch: %s", exc)
        return None
