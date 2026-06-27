"""Serviço de papéis de usuário e permissões por módulo."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from core.auth.system_modules import (
    SYSTEM_MODULES,
    default_module_permissions,
    merge_module_permissions,
    normalize_module_permissions,
)
from core.database.models import User, UserRoleDefinition

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")

SYSTEM_ROLE_SEEDS = (
    {
        "slug": "admin",
        "label": "Administrador",
        "is_system": True,
        "module_permissions": default_module_permissions(full_access=True),
    },
    {
        "slug": "dev_user",
        "label": "Desenvolvedor",
        "is_system": True,
        "module_permissions": default_module_permissions(full_access=True),
    },
)


def validate_role_slug(slug: str) -> str:
    key = slug.strip().lower()
    if not SLUG_RE.match(key):
        raise ValueError(
            "Identificador inválido — use letras minúsculas, números e _ (ex: engenheiro_civil)"
        )
    return key


def get_role_definition(db: Session, slug: str) -> UserRoleDefinition | None:
    return db.query(UserRoleDefinition).filter(UserRoleDefinition.slug == slug).first()


def require_role_definition(db: Session, slug: str) -> UserRoleDefinition:
    role = get_role_definition(db, slug)
    if not role:
        raise ValueError(f"Tipo de usuário não encontrado: {slug}")
    return role


def effective_module_permissions(user: User, db: Session) -> dict:
    if user.role == "admin":
        return default_module_permissions(full_access=True)
    role_def = get_role_definition(db, user.role)
    role_perms = role_def.module_permissions if role_def else None
    user_perms = user.module_permissions
    return merge_module_permissions(role_perms, user_perms)


def user_public_dict(user: User, db: Session) -> dict:
    role_def = get_role_definition(db, user.role)
    perms = effective_module_permissions(user, db)
    return user.to_dict(
        module_permissions=perms,
        role_label=role_def.label if role_def else user.role,
    )


def seed_role_definitions(db: Session) -> None:
    for spec in SYSTEM_ROLE_SEEDS:
        existing = get_role_definition(db, spec["slug"])
        if existing:
            continue
        db.add(
            UserRoleDefinition(
                slug=spec["slug"],
                label=spec["label"],
                module_permissions=spec["module_permissions"],
                is_system=spec["is_system"],
            )
        )
    db.commit()


def list_roles(db: Session) -> list[dict]:
    roles = db.query(UserRoleDefinition).order_by(UserRoleDefinition.label).all()
    return [r.to_dict() for r in roles]


def create_role_definition(
    db: Session,
    *,
    slug: str,
    label: str,
    module_permissions: dict | None = None,
) -> UserRoleDefinition:
    key = validate_role_slug(slug)
    if get_role_definition(db, key):
        raise ValueError(f"Tipo de usuário já existe: {key}")
    role = UserRoleDefinition(
        slug=key,
        label=label.strip() or key,
        module_permissions=normalize_module_permissions(module_permissions),
        is_system=False,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def system_modules_catalog() -> list[dict]:
    return list(SYSTEM_MODULES)
