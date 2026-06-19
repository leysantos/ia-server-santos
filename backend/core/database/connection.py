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
    from core.database.migrate_workspace import migrate_workspace
    from core.database.models import Base

    Base.metadata.create_all(bind=engine)
    migrate_workspace(engine)


def is_db_enabled() -> bool:
    return DB_ENABLED
