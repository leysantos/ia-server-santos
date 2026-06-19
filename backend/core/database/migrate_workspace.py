"""Migração incremental — workspace (projetos, mensagens, arquivos)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def migrate_workspace(engine) -> None:
    """Adiciona colunas/tabelas do workspace sem quebrar instalações existentes."""
    from core.database.models import Base

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if "conversations" not in inspector.get_table_names():
        return

    existing_cols = {c["name"] for c in inspector.get_columns("conversations")}
    alters: list[str] = []

    if "title" not in existing_cols:
        alters.append("ADD COLUMN title VARCHAR(200)")
    if "message_count" not in existing_cols:
        alters.append("ADD COLUMN message_count INTEGER NOT NULL DEFAULT 0")
    if "project_id" not in existing_cols:
        alters.append("ADD COLUMN project_id UUID")

    if alters:
        ddl = "ALTER TABLE conversations " + ", ".join(alters)
        with engine.begin() as conn:
            conn.execute(text(ddl))
        logger.info("migrate_workspace: conversations atualizada (%s)", ", ".join(alters))

    # FK project_id — ignora se já existir
    if "project_id" in existing_cols or alters:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE conversations "
                        "ADD CONSTRAINT fk_conversations_project_id "
                        "FOREIGN KEY (project_id) REFERENCES projects(id) "
                        "ON DELETE SET NULL"
                    )
                )
        except Exception:
            pass

    # Título derivado para conversas legadas
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE conversations SET title = LEFT(input_text, 80) "
                "WHERE title IS NULL AND input_text IS NOT NULL"
            )
        )

    logger.info("migrate_workspace: concluída")
