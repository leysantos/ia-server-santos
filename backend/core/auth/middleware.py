"""Middleware HTTP — exige JWT em rotas protegidas quando AUTH_ENABLED=true."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config.settings import get_settings
from core.auth.jwt_tokens import decode_access_token
from core.database.connection import SessionLocal
from core.database.models import User

logger = logging.getLogger(__name__)

PUBLIC_PREFIXES = (
    "/health",
    "/auth/login",
    "/auth/status",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _is_public_path(path: str) -> bool:
    if path == "/":
        return True
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in PUBLIC_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        settings = get_settings()
        if not settings.auth_enabled:
            return await call_next(request)

        path = request.url.path
        if _is_public_path(path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Não autenticado"},
            )

        token = auth_header[7:].strip()
        db = SessionLocal()
        try:
            payload = decode_access_token(token)
            user_id = UUID(str(payload["sub"]))
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Usuário inativo ou não encontrado"},
                )
            request.state.user = user
        except Exception:
            logger.debug("Auth middleware: token rejeitado em %s", path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido ou expirado"},
            )
        finally:
            db.close()

        return await call_next(request)
