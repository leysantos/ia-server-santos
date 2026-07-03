"""Migração B27 — empresa_id em budget_documents."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def migrate_budget_tenant(engine) -> None:
    from core.database.models import Base

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if "budget_documents" not in inspector.get_table_names():
        logger.info("migrate_budget_tenant: budget_documents ausente")
        return

    existing_cols = {c["name"] for c in inspector.get_columns("budget_documents")}
    with engine.begin() as conn:
        if "empresa_id" not in existing_cols:
            conn.execute(text("ALTER TABLE budget_documents ADD COLUMN empresa_id UUID"))
            logger.info("migrate_budget_tenant: coluna empresa_id adicionada")

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE budget_documents "
                    "ADD CONSTRAINT fk_budget_documents_empresa_id "
                    "FOREIGN KEY (empresa_id) REFERENCES companies(id) ON DELETE SET NULL"
                )
            )
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_budget_documents_empresa_id "
                    "ON budget_documents (empresa_id)"
                )
            )
    except Exception:
        pass

    logger.info("migrate_budget_tenant: concluída")
