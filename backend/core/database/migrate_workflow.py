"""Migração incremental — módulo Workflow Projetos."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

_PROJECT_COLUMNS = (
    ("codigo", "VARCHAR(80)"),
    ("cliente", "VARCHAR(200)"),
    ("responsavel", "VARCHAR(200)"),
    ("disciplina", "VARCHAR(60)"),
    ("status", "VARCHAR(40) DEFAULT 'ativo'"),
    ("empresa_id", "UUID"),
    ("versao_atual", "VARCHAR(20) DEFAULT 'REV00'"),
    ("workflow_initialized", "BOOLEAN DEFAULT FALSE"),
)

_WORKFLOW_TABLES = (
    "companies",
    "company_templates",
    "company_stamps",
    "company_settings",
    "company_signatures",
    "workflow_events",
    "project_folders",
    "workflow_drawings",
    "workflow_sheets",
    "workflow_revisions",
    "workflow_versions",
    "workflow_templates",
    "workflow_deliveries",
    "workflow_jobs",
    "workflow_delivery_packages",
    "workflow_package_items",
)


def migrate_workflow(engine) -> None:
    """Cria tabelas workflow + colunas extras em projects."""
    import core.database.workflow_models  # noqa: F401 — registra mappers
    from core.database.models import Base

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    if "projects" in existing:
        project_cols = {c["name"] for c in inspector.get_columns("projects")}
        added_empresa_id = False
        with engine.begin() as conn:
            for col_name, col_type in _PROJECT_COLUMNS:
                if col_name not in project_cols:
                    try:
                        conn.execute(
                            text(
                                f"ALTER TABLE projects ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                            )
                        )
                        logger.info("migrate_workflow: coluna projects.%s adicionada", col_name)
                        if col_name == "empresa_id":
                            added_empresa_id = True
                    except Exception as exc:
                        logger.debug("migrate_workflow column %s skip: %s", col_name, exc)

            if added_empresa_id or "empresa_id" in project_cols:
                try:
                    conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_projects_empresa_id ON projects (empresa_id)"
                        )
                    )
                except Exception as exc:
                    logger.debug("migrate_workflow empresa_id index skip: %s", exc)

    if "workflow_events" in existing:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_workflow_events_project_created "
                        "ON workflow_events (project_id, created_at DESC)"
                    )
                )
        except Exception as exc:
            logger.debug("migrate_workflow events index skip: %s", exc)

    created = len([t for t in _WORKFLOW_TABLES if t in existing])
    logger.info("migrate_workflow: OK (%d tabelas workflow visíveis)", created)
