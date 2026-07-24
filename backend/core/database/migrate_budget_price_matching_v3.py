"""Migração — coluna price_bases em budget_price_matching_jobs."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def migrate_budget_price_matching_v3(engine) -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "budget_price_matching_jobs" not in tables:
        return

    cols = {c["name"] for c in insp.get_columns("budget_price_matching_jobs")}
    if "price_bases" in cols:
        logger.debug("migrate_budget_price_matching_v3: coluna já existe")
        return

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE budget_price_matching_jobs ADD COLUMN price_bases JSON")
        )
    logger.info("migrate_budget_price_matching_v3: price_bases adicionada")
