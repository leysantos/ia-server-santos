"""Migração incremental — FKs em tabelas de audit/orçamento."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def _add_fk_if_missing(engine, ddl: str, label: str) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text(ddl))
        logger.info("migrate_audit_fks: %s", label)
    except Exception:
        pass


def migrate_audit_fks(engine) -> None:
    """Adiciona colunas/FKs sem quebrar instalações existentes."""
    from core.database.models import Base

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "budget_documents" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("budget_documents")}
        if "project_id" not in existing_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE budget_documents ADD COLUMN project_id UUID"))
            logger.info("migrate_audit_fks: budget_documents.project_id adicionada")

        _add_fk_if_missing(
            engine,
            "ALTER TABLE budget_documents "
            "ADD CONSTRAINT fk_budget_documents_project_id "
            "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL",
            "FK budget_documents.project_id -> projects.id",
        )

    if "agent_simulations" in tables and "agent_proposals" in tables:
        _add_fk_if_missing(
            engine,
            "ALTER TABLE agent_simulations "
            "ADD CONSTRAINT fk_agent_simulations_proposal_id "
            "FOREIGN KEY (proposal_id) REFERENCES agent_proposals(id) ON DELETE SET NULL",
            "FK agent_simulations.proposal_id -> agent_proposals.id",
        )

    logger.info("migrate_audit_fks: concluída")
