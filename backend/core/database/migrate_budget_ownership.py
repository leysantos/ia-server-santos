"""Migração incremental — ownership e versionamento em budget_documents."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def migrate_budget_ownership(engine) -> None:
    """Adiciona user_id e version sem quebrar instalações existentes."""
    from core.database.models import Base

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if "budget_documents" not in inspector.get_table_names():
        logger.info("migrate_budget_ownership: tabela budget_documents ausente")
        return

    existing_cols = {c["name"] for c in inspector.get_columns("budget_documents")}

    with engine.begin() as conn:
        if "user_id" not in existing_cols:
            conn.execute(text("ALTER TABLE budget_documents ADD COLUMN user_id UUID"))
            logger.info("migrate_budget_ownership: coluna user_id adicionada")

        if "version" not in existing_cols:
            conn.execute(
                text("ALTER TABLE budget_documents ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            )
            logger.info("migrate_budget_ownership: coluna version adicionada")

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE budget_documents "
                    "ADD CONSTRAINT fk_budget_documents_user_id "
                    "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL"
                )
            )
        logger.info("migrate_budget_ownership: FK user_id -> users.id")
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_budget_documents_user_id ON budget_documents (user_id)")
            )
    except Exception:
        pass

    logger.info("migrate_budget_ownership: concluída")
