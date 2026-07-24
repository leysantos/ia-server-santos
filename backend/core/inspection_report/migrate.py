"""Migração / seed de templates de laudo."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from core.inspection_report.typology import template_seed_payload
from core.inspection_report.constants import TEMPLATE_DEFS

logger = logging.getLogger(__name__)


def migrate_inspection_reports(engine: Engine) -> None:
    """Cria tabelas do módulo e faz seed/atualiza dos templates padrão."""
    from core.database.models import Base
    import core.inspection_report.models  # noqa: F401

    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables["inspection_report_templates"],
            Base.metadata.tables["inspection_reports"],
            Base.metadata.tables["inspection_report_assets"],
        ],
    )
    _ensure_project_id_column(engine)
    _seed_templates(engine)
    logger.info("inspection_reports: migrate + seed OK")


def _ensure_project_id_column(engine: Engine) -> None:
    inspector = inspect(engine)
    if "inspection_reports" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("inspection_reports")}
    if "project_id" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE inspection_reports ADD COLUMN project_id UUID"))
    logger.info("inspection_reports: coluna project_id adicionada")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE inspection_reports "
                    "ADD CONSTRAINT fk_inspection_reports_project_id "
                    "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL"
                )
            )
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_inspection_reports_project_id "
                    "ON inspection_reports (project_id)"
                )
            )
    except Exception:
        pass


def _seed_templates(engine: Engine) -> None:
    from core.inspection_report.models import InspectionReportTemplate

    with Session(engine) as session:
        by_slug = {t.slug: t for t in session.query(InspectionReportTemplate).all()}
        for item in TEMPLATE_DEFS:
            chapters, prompt = template_seed_payload(item)
            existing = by_slug.get(item["slug"])
            if existing:
                existing.name = item["name"]
                existing.description = item["description"]
                existing.discipline_hint = item["discipline_hint"]
                existing.chapters = chapters
                existing.system_prompt = prompt
                existing.active = True
            else:
                session.add(
                    InspectionReportTemplate(
                        slug=item["slug"],
                        name=item["name"],
                        description=item["description"],
                        discipline_hint=item["discipline_hint"],
                        chapters=chapters,
                        system_prompt=prompt,
                        active=True,
                    )
                )
        session.commit()
