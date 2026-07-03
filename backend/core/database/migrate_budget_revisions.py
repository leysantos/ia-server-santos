"""Migração — colunas de revisão/aditivo em budget_documents (B6)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def migrate_budget_revisions(engine) -> None:
    inspector = inspect(engine)
    if "budget_documents" not in inspector.get_table_names():
        logger.info("migrate_budget_revisions: tabela budget_documents ausente")
        return

    existing_cols = {c["name"] for c in inspector.get_columns("budget_documents")}

    with engine.begin() as conn:
        if "baseline_document_id" not in existing_cols:
            conn.execute(
                text("ALTER TABLE budget_documents ADD COLUMN baseline_document_id UUID")
            )
            logger.info("migrate_budget_revisions: baseline_document_id adicionada")

        if "revision_number" not in existing_cols:
            conn.execute(
                text(
                    "ALTER TABLE budget_documents ADD COLUMN revision_number INTEGER NOT NULL DEFAULT 0"
                )
            )
            logger.info("migrate_budget_revisions: revision_number adicionada")

        if "revision_label" not in existing_cols:
            conn.execute(
                text("ALTER TABLE budget_documents ADD COLUMN revision_label VARCHAR(80)")
            )
            logger.info("migrate_budget_revisions: revision_label adicionada")

        if "baseline_frozen_at" not in existing_cols:
            conn.execute(
                text("ALTER TABLE budget_documents ADD COLUMN baseline_frozen_at TIMESTAMPTZ")
            )
            logger.info("migrate_budget_revisions: baseline_frozen_at adicionada")

        if "baseline_snapshot" not in existing_cols:
            conn.execute(text("ALTER TABLE budget_documents ADD COLUMN baseline_snapshot JSON"))
            logger.info("migrate_budget_revisions: baseline_snapshot adicionada")

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_budget_documents_baseline_id "
                    "ON budget_documents (baseline_document_id)"
                )
            )
    except Exception:
        pass

    logger.info("migrate_budget_revisions: concluída")
