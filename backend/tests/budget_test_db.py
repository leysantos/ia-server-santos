"""Rebind SQLAlchemy engine para testes com sqlite (evita PostgreSQL do ambiente)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def rebind_test_database(database_url: str) -> None:
    import core.database.connection as conn

    conn.engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    conn.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=conn.engine)
