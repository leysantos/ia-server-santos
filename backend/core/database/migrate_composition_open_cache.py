"""Migração — cache global composition_open_cache (B32) + import legado."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def migrate_composition_open_cache(engine) -> None:
    from core.database.models import CompositionOpenCache

    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "composition_open_cache" not in tables:
        CompositionOpenCache.__table__.create(bind=engine, checkfirst=True)
        logger.info("migrate_composition_open_cache: tabela composition_open_cache criada")
    else:
        logger.debug("migrate_composition_open_cache: tabela já existe")

    if "budget_composition_snapshots" not in tables:
        return

    dialect = engine.dialect.name
    if dialect != "postgresql":
        return

    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO composition_open_cache (
                    id, composition_code, reference, uf, detail_json, hit_count, captured_at, updated_at
                )
                SELECT DISTINCT ON (composition_code, reference, uf)
                    gen_random_uuid(),
                    composition_code,
                    reference,
                    uf,
                    detail_json,
                    0,
                    captured_at,
                    captured_at
                FROM budget_composition_snapshots
                ORDER BY composition_code, reference, uf, captured_at DESC
                ON CONFLICT ON CONSTRAINT uq_comp_open_cache_code_ref_uf DO NOTHING
                """
            )
        )
        imported = result.rowcount or 0
        if imported:
            logger.info(
                "migrate_composition_open_cache: importados %s registros do legado",
                imported,
            )
