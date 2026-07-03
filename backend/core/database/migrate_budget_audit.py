"""Migração — tabela budget_audit_log (B7)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def migrate_budget_audit(engine) -> None:
    from core.database.models import BudgetAuditLog

    insp = inspect(engine)
    if "budget_audit_log" in insp.get_table_names():
        logger.debug("migrate_budget_audit: tabela já existe")
        return

    BudgetAuditLog.__table__.create(bind=engine, checkfirst=True)
    logger.info("migrate_budget_audit: tabela budget_audit_log criada")
