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
    from core.database.migrate_audit_fks import migrate_audit_fks
    from core.database.migrate_project_memory import migrate_project_memory
    from core.database.migrate_project_review import migrate_project_review
    from core.database.migrate_workflow import migrate_workflow
    from core.database.migrate_workspace import migrate_workspace
    from core.database.models import Base
    import core.database.workflow_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_workspace(engine)
    migrate_audit_fks(engine)
    migrate_project_review(engine)
    migrate_project_memory(engine)
    migrate_workflow(engine)
    migrate_auth(engine)
    migrate_user_roles(engine)


def is_db_enabled() -> bool:
    return DB_ENABLED
