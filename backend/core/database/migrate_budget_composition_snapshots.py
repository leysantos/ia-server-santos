"""Migração — tabela budget_composition_snapshots (orçamento analítico)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def migrate_budget_composition_snapshots(engine) -> None:
    from core.database.models import BudgetCompositionSnapshot

    insp = inspect(engine)
    if "budget_composition_snapshots" in insp.get_table_names():
        logger.debug("migrate_budget_composition_snapshots: tabela já existe")
        return

    BudgetCompositionSnapshot.__table__.create(bind=engine, checkfirst=True)
    logger.info(
        "migrate_budget_composition_snapshots: tabela budget_composition_snapshots criada"
    )
