"""Migração e seed inicial de usuários."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from config.settings import get_settings
from core.auth.passwords import hash_password
from core.database.models import Base, User

logger = logging.getLogger(__name__)

SEED_USERS = (
    {
        "username": "admin",
        "email": "admin@iaserver.local",
        "full_name": "Administrador",
        "role": "admin",
        "password_key": "admin",
    },
    {
        "username": "dev_user1",
        "email": "dev1@iaserver.local",
        "full_name": "Desenvolvedor 1",
        "role": "dev_user",
        "password_key": "dev",
    },
    {
        "username": "dev_user2",
        "email": "dev2@iaserver.local",
        "full_name": "Desenvolvedor 2",
        "role": "dev_user",
        "password_key": "dev",
    },
)


def _seed_password(password_key: str) -> str:
    settings = get_settings()
    if password_key == "admin":
        return settings.auth_seed_admin_password
    return settings.auth_seed_dev_password


def migrate_auth(engine) -> None:
    """Cria tabela users e insere usuários padrão se vazia."""
    Base.metadata.create_all(bind=engine, tables=[User.__table__])

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        logger.warning("migrate_auth: tabela users não criada")
        return

    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0

    if count > 0:
        logger.info("migrate_auth: %s usuário(s) existente(s), seed ignorado", count)
        return

    from core.database.connection import SessionLocal

    db = SessionLocal()
    try:
        for spec in SEED_USERS:
            user = User(
                username=spec["username"],
                email=spec["email"],
                full_name=spec["full_name"],
                role=spec["role"],
                password_hash=hash_password(_seed_password(spec["password_key"])),
                is_active=True,
            )
            db.add(user)
        db.commit()
        logger.info("migrate_auth: seed de %s usuários concluído", len(SEED_USERS))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
