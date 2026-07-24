"""
Conexão PostgreSQL via SQLAlchemy.

Pronto para injeção de dependência em FastAPI:

    from core.database.connection import get_db

    @app.get("/history")
    def history(db: Session = Depends(get_db)):
        ...
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DATABASE_URL, DB_ENABLED

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency generator para FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager para uso fora do FastAPI."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Cria todas as tabelas definidas nos models."""
    from core.database.migrate_auth import migrate_auth
    from core.database.migrate_user_roles import migrate_user_roles
    from core.database.migrate_budget_ownership import migrate_budget_ownership
    from core.database.migrate_budget_audit import migrate_budget_audit
    from core.database.migrate_budget_session_snapshot import migrate_budget_session_snapshot
    from core.database.migrate_budget_composition_snapshots import migrate_budget_composition_snapshots
    from core.database.migrate_composition_open_cache import migrate_composition_open_cache
    from core.database.migrate_budget_revisions import migrate_budget_revisions
    from core.database.migrate_budget_tenant import migrate_budget_tenant
    from core.database.migrate_budget_session_lock import migrate_budget_session_lock
    from core.database.migrate_budget_price_matching import migrate_budget_price_matching
    from core.database.migrate_budget_price_matching_v2 import migrate_budget_price_matching_v2
    from core.database.migrate_budget_price_matching_v3 import migrate_budget_price_matching_v3
    from core.database.migrate_audit_fks import migrate_audit_fks
    from core.database.migrate_project_memory import migrate_project_memory
    from core.database.migrate_project_review import migrate_project_review
    from core.database.migrate_workflow import migrate_workflow
    from core.database.migrate_workspace import migrate_workspace
    from core.inspection_report.migrate import migrate_inspection_reports
    from core.database.models import Base
    import core.database.workflow_models  # noqa: F401
    import core.inspection_report.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_workspace(engine)
    migrate_audit_fks(engine)
    migrate_budget_ownership(engine)
    migrate_budget_audit(engine)
    migrate_budget_session_snapshot(engine)
    migrate_budget_composition_snapshots(engine)
    migrate_composition_open_cache(engine)
    migrate_budget_revisions(engine)
    migrate_project_review(engine)
    migrate_project_memory(engine)
    migrate_workflow(engine)
    migrate_budget_tenant(engine)
    migrate_budget_session_lock(engine)
    migrate_budget_price_matching(engine)
    migrate_budget_price_matching_v2(engine)
    migrate_budget_price_matching_v3(engine)
    migrate_auth(engine)
    migrate_user_roles(engine)
    migrate_inspection_reports(engine)


def is_db_enabled() -> bool:
    return DB_ENABLED
