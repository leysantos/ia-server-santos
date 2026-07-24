"""Migração — tabelas budget_price_matching_jobs e budget_price_matching."""

from __future__ import annotations

import logging

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def migrate_budget_price_matching(engine) -> None:
    from core.database.models import BudgetPriceMatching, BudgetPriceMatchingJob

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "budget_price_matching_jobs" not in tables:
        BudgetPriceMatchingJob.__table__.create(bind=engine, checkfirst=True)
        logger.info("migrate_budget_price_matching: budget_price_matching_jobs criada")
    if "budget_price_matching" not in tables:
        BudgetPriceMatching.__table__.create(bind=engine, checkfirst=True)
        logger.info("migrate_budget_price_matching: budget_price_matching criada")
