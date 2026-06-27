"""Validação de JWT e senhas seed antes de exposição externa (tunnel/LAN)."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import AppSettings

logger = logging.getLogger(__name__)

DEFAULT_JWT_SECRET = "change-me-jwt-secret-in-production"
DEFAULT_ADMIN_PASSWORD = "Admin@2026!"
DEFAULT_DEV_PASSWORD = "Dev@2026!"
MIN_JWT_SECRET_LEN = 32


def collect_auth_hardening_issues(settings: AppSettings) -> list[str]:
    """Retorna avisos de configuração insegura (lista vazia = OK)."""
    if not settings.auth_enabled:
        return []

    issues: list[str] = []

    secret = (settings.jwt_secret or "").strip()
    if secret == DEFAULT_JWT_SECRET:
        issues.append(
            "JWT_SECRET ainda é o valor padrão — defina um segredo único "
            f"(mín. {MIN_JWT_SECRET_LEN} caracteres) antes de uso via tunnel"
        )
    elif len(secret) < MIN_JWT_SECRET_LEN:
        issues.append(
            f"JWT_SECRET curto ({len(secret)} chars) — use pelo menos {MIN_JWT_SECRET_LEN}"
        )

    if settings.auth_seed_admin_password == DEFAULT_ADMIN_PASSWORD:
        issues.append(
            "AUTH_SEED_ADMIN_PASSWORD ainda é a senha padrão — altere em produção/tunnel"
        )

    if settings.auth_seed_dev_password == DEFAULT_DEV_PASSWORD:
        issues.append(
            "AUTH_SEED_DEV_PASSWORD ainda é a senha padrão — altere em produção/tunnel"
        )

    return issues


def run_auth_hardening_check(settings: AppSettings) -> None:
    """Loga avisos ou falha o startup se AUTH_HARDENING_STRICT=true."""
    issues = collect_auth_hardening_issues(settings)
    if not issues:
        return

    strict = os.getenv("AUTH_HARDENING_STRICT", "").lower() in ("1", "true", "yes")
    for msg in issues:
        if strict:
            raise RuntimeError(f"Auth hardening: {msg}")
        logger.warning("AUTH HARDENING: %s", msg)
