"""Migração incremental — memória operacional (activity + decisions)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

_MEMORY_TABLES = (
    "project_activity_events",
    "project_decisions",
)


def migrate_project_memory(engine) -> None:
    """Cria tabelas de memória operacional via metadata + índices auxiliares."""
    from core.database.models import Base

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    if "project_activity_events" in existing:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_project_activity_project_created "
                        "ON project_activity_events (project_id, created_at DESC)"
                    )
                )
        except Exception as exc:
            logger.debug("migrate_project_memory activity index skip: %s", exc)

    if "project_decisions" in existing:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_project_decisions_project_created "
                        "ON project_decisions (project_id, created_at DESC)"
                    )
                )
        except Exception as exc:
            logger.debug("migrate_project_memory decisions index skip: %s", exc)

    logger.info("migrate_project_memory: tabelas OK (%s)", ", ".join(_MEMORY_TABLES))
