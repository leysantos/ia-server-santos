from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.settings import get_settings
from core.auth.dependencies import get_current_user, require_auth_user
from core.auth.jwt_tokens import create_access_token
from core.auth.passwords import hash_password, verify_password
from core.auth.system_modules import normalize_module_permissions
from core.auth.user_roles_service import (
    create_role_definition,
    effective_module_permissions,
    list_roles,
    require_role_definition,
    system_modules_catalog,
    user_public_dict,
    validate_role_slug,
)
from core.database.connection import get_db
from core.database.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ModulePermissionsPayload(BaseModel):
    hidden: bool = False
    blocked: bool = False


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=6, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    full_name: str | None = Field(default=None, max_length=200)
    role: str = Field(default="dev_user", max_length=40)
    is_active: bool = True
    module_permissions: dict[str, ModulePermissionsPayload] | None = None


class UserUpdateRequest(BaseModel):
    email: str | None = Field(default=None, max_length=200)
    full_name: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=200)
    module_permissions: dict[str, ModulePermissionsPayload] | None = None


class RoleCreateRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=40)
    label: str = Field(min_length=2, max_length=120)
    module_permissions: dict[str, ModulePermissionsPayload] | None = None


def _permissions_to_dict(
    raw: dict[str, ModulePermissionsPayload | dict[str, bool]] | None,
) -> dict[str, dict[str, bool]] | None:
    if raw is None:
        return None
    out: dict[str, dict[str, bool]] = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            out[key] = {
                "hidden": bool(val.get("hidden")),
                "blocked": bool(val.get("blocked")),
            }
        else:
            out[key] = {"hidden": bool(val.hidden), "blocked": bool(val.blocked)}
    return out


@router.get("/status")
def auth_status():
    settings = get_settings()
    return {
        "auth_enabled": settings.auth_enabled,
        "token_expire_minutes": settings.jwt_expire_minutes,
    }


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    if not get_settings().auth_enabled:
        raise HTTPException(status_code=400, detail="Autenticação desabilitada no servidor")

    username = body.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")

    token = create_access_token(user_id=user.id, username=user.username, role=user.role)
    return LoginResponse(access_token=token, user=user_public_dict(user, db))


@router.get("/me")
def auth_me(user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.auth_enabled:
        return {"auth_enabled": False, "user": None}
    if user is None:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return {"auth_enabled": True, "user": user_public_dict(user, db)}


def _require_admin(user: User | None = Depends(get_current_user)) -> User:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Autenticação desabilitada")
    if user is None:
        raise HTTPException(status_code=401, detail="Não autenticado")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user


@router.get("/modules")
def auth_modules_catalog(_admin: User = Depends(_require_admin)):
    return {"modules": system_modules_catalog()}


@router.get("/roles")
def auth_list_roles(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    return {"roles": list_roles(db)}


@router.post("/roles")
def auth_create_role(
    body: RoleCreateRequest,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        slug = validate_role_slug(body.slug)
        perms = normalize_module_permissions(_permissions_to_dict(body.module_permissions))
        role = create_role_definition(
            db,
            slug=slug,
            label=body.label.strip(),
            module_permissions=perms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"role": role.to_dict()}


@router.get("/users")
def list_users(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.username).all()
    return {"users": [user_public_dict(u, db) for u in users]}


@router.post("/users")
def create_user(
    body: UserCreateRequest,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    username = body.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Nome de usuário já existe")

    try:
        require_role_definition(db, body.role.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_perms = _permissions_to_dict(body.module_permissions)
    user = User(
        username=username,
        email=(body.email or "").strip() or None,
        full_name=(body.full_name or "").strip() or None,
        role=body.role.strip(),
        is_active=body.is_active,
        password_hash=hash_password(body.password),
        module_permissions=normalize_module_permissions(user_perms) if user_perms else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"user": user_public_dict(user, db)}


@router.patch("/users/{user_id}")
def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if body.role is not None and user.id == admin.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="Não é possível remover o próprio papel de admin")
    if body.is_active is False and user.id == admin.id:
        raise HTTPException(status_code=400, detail="Não é possível desativar o próprio usuário")

    patch = body.model_dump(exclude_unset=True)
    password = patch.pop("password", None)
    patch.pop("module_permissions", None)
    if "role" in patch and patch["role"] is not None:
        try:
            require_role_definition(db, patch["role"].strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    for key, value in patch.items():
        setattr(user, key, value)
    if body.module_permissions is not None:
        user.module_permissions = normalize_module_permissions(
            _permissions_to_dict(body.module_permissions)
        )
    if password:
        user.password_hash = hash_password(password)

    db.commit()
    db.refresh(user)
    return {"user": user_public_dict(user, db)}


@router.delete("/users/{user_id}")
def deactivate_user(
    user_id: UUID,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Não é possível desativar o próprio usuário")

    user.is_active = False
    db.commit()
    return {"ok": True, "user": user_public_dict(user, db)}
