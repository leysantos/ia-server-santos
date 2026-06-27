from __future__ import annotations

import shutil
import subprocess

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.auth.dependencies import require_admin, require_auth_user
from core.database.models import User
from core.system.network_access_store import (
    get_network_access_config,
    network_access_status,
    save_network_access_config,
)

router = APIRouter(prefix="/system", tags=["System"])


class InternalNetworkUpdate(BaseModel):
    enabled: bool | None = None
    host_ip: str | None = None
    api_port: int | None = Field(default=None, ge=1, le=65535)
    frontend_port: int | None = Field(default=None, ge=1, le=65535)
    api_base_url: str | None = None
    frontend_url: str | None = None
    allowed_cidrs: list[str] | None = None
    bind_api_all_interfaces: bool | None = None
    notes: str | None = None


class CloudflareAccessUpdate(BaseModel):
    enabled: bool | None = None
    tunnel_name: str | None = None
    tunnel_id: str | None = None
    tunnel_token: str | None = None
    account_id: str | None = None
    zone_id: str | None = None
    public_hostname: str | None = None
    public_api_url: str | None = None
    public_frontend_url: str | None = None
    access_application_name: str | None = None
    access_policy: str | None = None
    warp_required: bool | None = None
    notes: str | None = None


class NetworkAccessUpdateRequest(BaseModel):
    internal: InternalNetworkUpdate | None = None
    cloudflare: CloudflareAccessUpdate | None = None
    cors_extra_origins: list[str] | None = None


@router.get("/network-access")
def get_network_access(_user: User = Depends(require_auth_user)):
    return network_access_status()


@router.patch("/network-access")
def patch_network_access(
    body: NetworkAccessUpdateRequest,
    _admin: User = Depends(require_admin),
):
    payload: dict = {}
    if body.internal is not None:
        payload["internal"] = body.internal.model_dump(exclude_unset=True)
    if body.cloudflare is not None:
        payload["cloudflare"] = body.cloudflare.model_dump(exclude_unset=True)
    if body.cors_extra_origins is not None:
        payload["cors_extra_origins"] = body.cors_extra_origins

    config = save_network_access_config(payload)
    status = network_access_status()
    status["restart_hint"] = (
        "Reinicie a API após alterar CORS no .env. "
        "As origens sugeridas estão em suggested_cors_origins."
    )
    status["saved"] = True
    status["effective_access_mode"] = status.get("effective_access_mode")
    _ = config
    return status


def _cloudflared_running() -> bool:
    try:
        out = subprocess.run(
            ["pgrep", "-x", "cloudflared"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return out.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@router.get("/network-access/quick-tunnel")
def get_quick_tunnel(_user: User = Depends(require_auth_user)):
    from core.system.quick_tunnel_service import quick_tunnel_status

    return quick_tunnel_status()


@router.post("/network-access/quick-tunnel/start")
def start_quick_tunnel_route(_admin: User = Depends(require_admin)):
    from core.system.quick_tunnel_service import start_quick_tunnel
    from fastapi import HTTPException

    try:
        return start_quick_tunnel()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/network-access/quick-tunnel/stop")
def stop_quick_tunnel_route(_admin: User = Depends(require_admin)):
    from core.system.quick_tunnel_service import stop_quick_tunnel

    return stop_quick_tunnel()


@router.get("/network-access/cloudflare/status")
def cloudflare_tunnel_status(_user: User = Depends(require_auth_user)):
    cfg = get_network_access_config()
    binary = shutil.which("cloudflared")
    return {
        "cloudflared_installed": bool(binary),
        "cloudflared_path": binary,
        "tunnel_running": _cloudflared_running(),
        "cloudflare": cfg.to_dict(mask_secrets=True).get("cloudflare"),
        "setup_hint": "WSL: make cloudflare-setup  |  Token: Configurações → Acesso e rede",
        "run_hint": "make cloudflare-run  (ou systemctl --user start cloudflared-ia-server)",
    }
