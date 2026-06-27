"""Catálogo de módulos do sistema e permissões de acesso."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict


class ModulePermission(TypedDict):
    hidden: bool
    blocked: bool


class SystemModule(TypedDict):
    id: str
    label: str
    description: str


SYSTEM_MODULES: list[SystemModule] = [
    {"id": "chat", "label": "Chat IA", "description": "Assistente single-domain"},
    {"id": "orchestrate", "label": "Orquestrador", "description": "Multi-disciplinar"},
    {"id": "copilot", "label": "Copilot", "description": "Planejamento IA"},
    {"id": "aed", "label": "AED", "description": "Design autônomo"},
    {"id": "projects", "label": "Projetos", "description": "Workspace"},
    {"id": "budget", "label": "Orçamento", "description": "Pricing Engine"},
    {"id": "console", "label": "Console", "description": "Operações e GPU"},
    {"id": "history", "label": "Histórico", "description": "Conversas salvas"},
    {"id": "settings", "label": "Configurações", "description": "Administração do sistema"},
]

SYSTEM_MODULE_IDS = frozenset(m["id"] for m in SYSTEM_MODULES)


def default_module_permissions(*, full_access: bool = True) -> dict[str, ModulePermission]:
    perms: dict[str, ModulePermission] = {}
    for mod in SYSTEM_MODULES:
        if full_access:
            perms[mod["id"]] = {"hidden": False, "blocked": False}
        else:
            perms[mod["id"]] = {"hidden": False, "blocked": True}
    return perms


def normalize_module_permissions(raw: dict[str, Any] | None) -> dict[str, ModulePermission]:
    base = default_module_permissions(full_access=True)
    if not raw:
        return base
    for mod_id in SYSTEM_MODULE_IDS:
        entry = raw.get(mod_id)
        if not isinstance(entry, dict):
            continue
        base[mod_id] = {
            "hidden": bool(entry.get("hidden")),
            "blocked": bool(entry.get("blocked")),
        }
    return base


def merge_module_permissions(
    role_permissions: dict[str, ModulePermission] | None,
    user_permissions: dict[str, ModulePermission] | None,
) -> dict[str, ModulePermission]:
    merged = normalize_module_permissions(role_permissions)
    if user_permissions:
        user_norm = normalize_module_permissions(user_permissions)
        for mod_id in SYSTEM_MODULE_IDS:
            merged[mod_id] = deepcopy(user_norm[mod_id])
    return merged


def module_access_state(perm: ModulePermission) -> str:
    if perm["hidden"]:
        return "oculto"
    if perm["blocked"]:
        return "visivel_bloqueado"
    return "liberado"
