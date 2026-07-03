"""Migração B28 — lock de edição concorrente por session_id."""

from __future__ import annotations

import logging

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def migrate_budget_session_lock(engine) -> None:
    from core.database.models import Base, BudgetSessionLock

    inspector = inspect(engine)
    if "budget_session_locks" not in inspector.get_table_names():
        BudgetSessionLock.__table__.create(bind=engine, checkfirst=True)
        logger.info("migrate_budget_session_lock: tabela budget_session_locks criada")
    else:
        logger.debug("migrate_budget_session_lock: tabela já existe")
