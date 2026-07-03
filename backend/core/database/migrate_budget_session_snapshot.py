"""Migração — tabela budget_session_snapshots (B18)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def migrate_budget_session_snapshot(engine) -> None:
    from core.database.models import BudgetSessionSnapshot

    insp = inspect(engine)
    if "budget_session_snapshots" in insp.get_table_names():
        logger.debug("migrate_budget_session_snapshot: tabela já existe")
        return

    BudgetSessionSnapshot.__table__.create(bind=engine, checkfirst=True)
    logger.info("migrate_budget_session_snapshot: tabela budget_session_snapshots criada")
