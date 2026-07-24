"""Migração — colunas session_id, hierarchy em jobs e row_type em linhas."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def migrate_budget_price_matching_v2(engine) -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "budget_price_matching_jobs" in tables:
        cols = {c["name"] for c in insp.get_columns("budget_price_matching_jobs")}
        with engine.begin() as conn:
            if "session_id" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE budget_price_matching_jobs "
                        "ADD COLUMN session_id VARCHAR(64)"
                    )
                )
                logger.info("migrate_budget_price_matching_v2: session_id adicionada")
            if "hierarchy" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE budget_price_matching_jobs "
                        "ADD COLUMN hierarchy JSON"
                    )
                )
                logger.info("migrate_budget_price_matching_v2: hierarchy adicionada")

    if "budget_price_matching" in tables:
        cols = {c["name"] for c in insp.get_columns("budget_price_matching")}
        if "row_type" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE budget_price_matching "
                        "ADD COLUMN row_type VARCHAR(20)"
                    )
                )
            logger.info("migrate_budget_price_matching_v2: row_type adicionada")
