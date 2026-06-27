"""Cloudflare Quick Tunnel (*.trycloudflare.com) — sem domínio próprio."""

from __future__ import annotations

import json
import logging
import re
import shutil
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import DATA_DIR
from core.system.network_access_store import get_network_access_config, save_network_access_config

logger = logging.getLogger(__name__)

SYSTEM_DIR = DATA_DIR / "system"
STATE_PATH = SYSTEM_DIR / "quick_tunnel_state.json"
API_LOG = SYSTEM_DIR / "cloudflared-api.log"
FE_LOG = SYSTEM_DIR / "cloudflared-frontend.log"

URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
QUICK_TUNNEL_MARKER = "cloudflared tunnel --url http://localhost:"


def _ensure_dir() -> None:
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)


def cloudflared_installed() -> bool:
    return shutil.which("cloudflared") is not None


def _read_state() -> dict[str, Any]:
    _ensure_dir()
    if not STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(data: dict[str, Any]) -> None:
    _ensure_dir()
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        import os

        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _extract_url_from_log(log_path: Path, timeout_sec: int = 35) -> str | None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if log_path.exists():
            text = log_path.read_text(encoding="utf-8", errors="replace")
            match = URL_PATTERN.search(text)
            if match:
                return match.group(0)
        time.sleep(1)
    return None


def _kill_quick_tunnels() -> None:
    try:
        subprocess.run(
            ["pkill", "-f", QUICK_TUNNEL_MARKER],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    state = _read_state()
    for key in ("api_pid", "frontend_pid"):
        pid = state.get(key)
        if isinstance(pid, int) and _pid_alive(pid):
            try:
                import os

                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass


def _sync_network_access(api_url: str, frontend_url: str, *, active: bool) -> None:
    patch: dict[str, Any] = {
        "cloudflare": {
            "enabled": active,
            "tunnel_name": "quick-tunnel-trycloudflare" if active else "",
            "notes": (
                "Acesso temporário trycloudflare.com (sem domínio próprio)"
                if active
                else "Quick Tunnel parado"
            ),
            "public_api_url": api_url if active else "",
            "public_frontend_url": frontend_url if active else "",
            "public_hostname": frontend_url.replace("https://", "").split("/")[0] if active else "",
        }
    }
    current = get_network_access_config()
    origins = list(current.cors_extra_origins)
    for url in (api_url, frontend_url):
        u = url.rstrip("/")
        if active and u and u not in origins:
            origins.append(u)
        if not active and u in origins:
            origins.remove(u)
    patch["cors_extra_origins"] = origins
    save_network_access_config(patch)


def quick_tunnel_status() -> dict[str, Any]:
    state = _read_state()
    api_pid = state.get("api_pid")
    fe_pid = state.get("frontend_pid")
    api_alive = _pid_alive(api_pid if isinstance(api_pid, int) else None)
    fe_alive = _pid_alive(fe_pid if isinstance(fe_pid, int) else None)
    running = api_alive and fe_alive

    if not running and state.get("status") == "running":
        state = {**state, "status": "stopped"}
        _write_state(state)

    cfg = get_network_access_config()
    return {
        "cloudflared_installed": cloudflared_installed(),
        "running": running,
        "status": "running" if running else "stopped",
        "api_url": state.get("api_url") or cfg.cloudflare.public_api_url or "",
        "frontend_url": state.get("frontend_url") or cfg.cloudflare.public_frontend_url or "",
        "api_pid": api_pid if api_alive else None,
        "frontend_pid": fe_pid if fe_alive else None,
        "started_at": state.get("started_at"),
        "restart_hint": (
            "Reinicie o frontend (npm run dev) após iniciar o túnel. "
            "Na URL trycloudflare, a API é acessada via /api-backend no mesmo host — "
            "não é necessário alterar NEXT_PUBLIC_API_URL."
        ),
        "env_hint": (
            "Acesso externo: use só a URL do frontend (trycloudflare). "
            "A API é encaminhada automaticamente pelo proxy /api-backend."
            if running
            else ""
        ),
    }


def start_quick_tunnel(
    *,
    api_port: int = 8000,
    frontend_port: int = 3000,
) -> dict[str, Any]:
    if not cloudflared_installed():
        raise RuntimeError("cloudflared não está instalado no servidor.")

    _kill_quick_tunnels()
    _ensure_dir()
    API_LOG.write_text("", encoding="utf-8")
    FE_LOG.write_text("", encoding="utf-8")

    api_proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{api_port}"],
        stdout=open(API_LOG, "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    fe_proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{frontend_port}"],
        stdout=open(FE_LOG, "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    api_url = _extract_url_from_log(API_LOG)
    fe_url = _extract_url_from_log(FE_LOG)

    if not api_url or not fe_url:
        _kill_quick_tunnels()
        try:
            api_proc.kill()
            fe_proc.kill()
        except OSError:
            pass
        raise RuntimeError(
            "Não foi possível obter URLs trycloudflare. "
            "Verifique se API e frontend estão rodando (make api, npm run dev)."
        )

    started_at = datetime.now(UTC).isoformat()
    state = {
        "status": "running",
        "api_url": api_url,
        "frontend_url": fe_url,
        "api_pid": api_proc.pid,
        "frontend_pid": fe_proc.pid,
        "started_at": started_at,
    }
    _write_state(state)
    _sync_network_access(api_url, fe_url, active=True)

    logger.info("Quick tunnel iniciado: api=%s frontend=%s", api_url, fe_url)
    return {**quick_tunnel_status(), "message": "Túnel temporário iniciado com sucesso."}


def stop_quick_tunnel() -> dict[str, Any]:
    state = _read_state()
    api_url = str(state.get("api_url") or "")
    fe_url = str(state.get("frontend_url") or "")
    _kill_quick_tunnels()
    _write_state({"status": "stopped"})
    if api_url or fe_url:
        _sync_network_access(api_url, fe_url, active=False)
    return {**quick_tunnel_status(), "message": "Túnel temporário encerrado."}
