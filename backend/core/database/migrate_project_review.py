"""Migração incremental — Project Review Engine (digital twin, reviews, NCs)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

_REVIEW_TABLES = (
    "project_digital_twin",
    "project_reviews",
    "project_nonconformities",
    "project_document_extractions",
)


def migrate_project_review(engine) -> None:
    """Cria tabelas do Project Review Engine via metadata + índices auxiliares."""
    from core.database.models import Base

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    if "project_reviews" in existing:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_project_reviews_project_version "
                        "ON project_reviews (project_id, version DESC)"
                    )
                )
        except Exception as exc:
            logger.debug("migrate_project_review index skip: %s", exc)

    created = [t for t in _REVIEW_TABLES if t in existing or t in inspector.get_table_names()]
    logger.info("migrate_project_review: tabelas OK (%s)", ", ".join(_REVIEW_TABLES))
