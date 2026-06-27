"""Migração — tipos de usuário e permissões por módulo."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from core.auth.user_roles_service import seed_role_definitions
from core.database.models import Base, User, UserRoleDefinition

logger = logging.getLogger(__name__)


def migrate_user_roles(engine) -> None:
    Base.metadata.create_all(bind=engine, tables=[UserRoleDefinition.__table__])

    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "module_permissions" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN module_permissions JSON"))
            logger.info("migrate_user_roles: coluna users.module_permissions adicionada")

    from core.database.connection import SessionLocal

    db = SessionLocal()
    try:
        seed_role_definitions(db)
        logger.info("migrate_user_roles: papéis do sistema garantidos")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
