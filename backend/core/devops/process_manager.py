"""Gerenciamento de processos de desenvolvimento (serviços locais)."""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from config.settings import BASE_DIR, get_settings

REPO_ROOT = BASE_DIR.parent
DEVOPS_DIR = BASE_DIR / "data" / "devops"
PID_FILE = DEVOPS_DIR / "processes.json"
LOG_DIR = DEVOPS_DIR / "logs"
DOCKER_DIR = REPO_ROOT / "infra" / "docker"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


@dataclass(frozen=True)
class ServiceSpec:
    id: str
    label: str
    description: str
    group: str  # core | optional | external
    port: int | None = None
    managed: bool = True  # pode start/stop via UI


SERVICE_SPECS: tuple[ServiceSpec, ...] = (
    ServiceSpec(
        id="postgres",
        label="PostgreSQL",
        description="Banco de dados (Docker :5433)",
        group="core",
        port=5433,
    ),
    ServiceSpec(
        id="api",
        label="API FastAPI",
        description="Backend uvicorn (:8000) — make api",
        group="core",
        port=8000,
        managed=False,
    ),
    ServiceSpec(
        id="frontend",
        label="Frontend Next.js",
        description="Interface web (:3000) — npm run dev",
        group="core",
        port=3000,
    ),
    ServiceSpec(
        id="ollama",
        label="Ollama",
        description="LLM local (:11434)",
        group="core",
        port=11434,
        managed=False,
    ),
    ServiceSpec(
        id="redis",
        label="Redis",
        description="Fila workflow (:6379)",
        group="optional",
        port=6379,
    ),
    ServiceSpec(
        id="minio",
        label="MinIO",
        description="Object storage workflow (:9000)",
        group="optional",
        port=9000,
    ),
    ServiceSpec(
        id="celery",
        label="Celery Worker",
        description="Worker workflow (opcional)",
        group="optional",
    ),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except (URLError, OSError, ValueError):
        return False


def _load_pids() -> dict[str, Any]:
    DEVOPS_DIR.mkdir(parents=True, exist_ok=True)
    if not PID_FILE.exists():
        return {}
    try:
        return json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_pids(data: dict[str, Any]) -> None:
    DEVOPS_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _docker_container_running(name: str) -> bool:
    if not shutil_which("docker"):
        return False
    proc = subprocess.run(
        ["docker", "ps", "--filter", f"name={name}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return name in (proc.stdout or "")


def shutil_which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


class ProcessManager:
    def list_services(self) -> list[dict[str, Any]]:
        pids = _load_pids()
        items: list[dict[str, Any]] = []
        for spec in SERVICE_SPECS:
            items.append(self._service_status(spec, pids.get(spec.id)))
        return items

    def _service_status(self, spec: ServiceSpec, meta: dict | None) -> dict[str, Any]:
        status = "unknown"
        detail = ""
        pid = None
        log_file = None

        if spec.id == "postgres":
            running = _docker_container_running("ia_server_santos_db")
            status = "running" if running else "stopped"
            detail = "container ia_server_santos_db"
        elif spec.id == "redis":
            running = _docker_container_running("ia_server_santos_redis")
            status = "running" if running else "stopped"
        elif spec.id == "minio":
            running = _docker_container_running("ia_server_santos_minio")
            status = "running" if running else "stopped"
        elif spec.id == "api":
            if _http_ok("http://127.0.0.1:8000/health"):
                status = "running"
                detail = "GET /health OK"
            elif spec.port and _port_open("127.0.0.1", spec.port):
                status = "running"
            else:
                status = "stopped"
        elif spec.id == "ollama":
            base = get_settings().ollama_base_url.rstrip("/")
            if _http_ok(f"{base}/api/tags"):
                status = "running"
            else:
                status = "stopped"
            detail = base
        elif meta:
            pid = meta.get("pid")
            log_file = meta.get("log_file")
            if pid and _pid_alive(int(pid)):
                status = "running"
            else:
                status = "stopped"
                detail = "processo encerrado"
        elif spec.port and _port_open("127.0.0.1", spec.port):
            status = "running"
            detail = f"porta {spec.port} em uso (externo)"
        else:
            status = "stopped"

        return {
            "id": spec.id,
            "label": spec.label,
            "description": spec.description,
            "group": spec.group,
            "port": spec.port,
            "managed": spec.managed,
            "status": status,
            "detail": detail,
            "pid": pid,
            "log_file": log_file,
            "can_start": spec.managed and status != "running",
            "can_stop": spec.managed and status == "running" and spec.id != "api",
        }

    def start_service(self, service_id: str) -> dict[str, Any]:
        spec = self._get_spec(service_id)
        if not spec.managed:
            raise ValueError(f"Serviço '{service_id}' não é iniciado pela UI (externo ou já ativo)")
        if service_id == "postgres":
            return self._start_postgres()
        if service_id == "frontend":
            return self._start_frontend()
        if service_id == "redis" or service_id == "minio":
            return self._start_workflow_infra(service_id)
        if service_id == "celery":
            return self._start_celery()
        raise ValueError(f"Serviço desconhecido ou sem start: {service_id}")

    def stop_service(self, service_id: str) -> dict[str, Any]:
        spec = self._get_spec(service_id)
        if not spec.managed:
            raise ValueError(f"Serviço '{service_id}' não pode ser parado pela UI")
        if service_id == "postgres":
            return self._stop_docker_service("ia_server_santos_db", service_id)
        if service_id == "redis":
            return self._stop_docker_service("ia_server_santos_redis", service_id)
        if service_id == "minio":
            return self._stop_docker_service("ia_server_santos_minio", service_id)
        return self._stop_process(service_id)

    def start_core_stack(self) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        order = ["postgres"]
        for sid in order:
            svc = self._service_status(self._get_spec(sid), _load_pids().get(sid))
            if svc["status"] == "running":
                results.append({"id": sid, "action": "skip", "message": "já em execução"})
                continue
            try:
                results.append({"id": sid, "action": "start", **self.start_service(sid)})
            except Exception as exc:
                results.append({"id": sid, "action": "error", "error": str(exc)})
        # db-init se postgres subiu
        if any(r.get("action") == "start" and r.get("id") == "postgres" for r in results):
            try:
                self._run_db_init()
                results.append({"id": "db-init", "action": "ok", "message": "tabelas verificadas"})
            except Exception as exc:
                results.append({"id": "db-init", "action": "error", "error": str(exc)})
        return {"results": results, "services": self.list_services()}

    @staticmethod
    def _get_spec(service_id: str) -> ServiceSpec:
        for spec in SERVICE_SPECS:
            if spec.id == service_id:
                return spec
        raise ValueError(f"Serviço não encontrado: {service_id}")

    def _start_postgres(self) -> dict[str, Any]:
        if not DOCKER_DIR.is_dir():
            raise FileNotFoundError(f"Pasta Docker não encontrada: {DOCKER_DIR}")
        proc = subprocess.run(
            ["docker", "compose", "up", "-d", "postgres"],
            cwd=str(DOCKER_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "docker compose falhou")
        return {"status": "started", "message": "PostgreSQL iniciado"}

    def _start_workflow_infra(self, service_id: str) -> dict[str, Any]:
        service = "redis" if service_id == "redis" else "minio"
        proc = subprocess.run(
            ["docker", "compose", "up", "-d", service],
            cwd=str(DOCKER_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "docker compose falhou")
        return {"status": "started", "message": f"{service} iniciado"}

    def _start_frontend(self) -> dict[str, Any]:
        frontend_dir = REPO_ROOT / "frontend"
        if not (frontend_dir / "package.json").exists():
            raise FileNotFoundError("frontend/package.json não encontrado")
        if not shutil_which("npm"):
            raise RuntimeError("npm não encontrado no PATH")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"frontend-{int(time.time())}.log"
        log_handle = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"],
            cwd=str(frontend_dir),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "FORCE_COLOR": "0"},
        )
        pids = _load_pids()
        pids["frontend"] = {
            "pid": proc.pid,
            "started_at": _utc_now(),
            "log_file": str(log_path),
        }
        _save_pids(pids)
        return {"status": "started", "pid": proc.pid, "log_file": str(log_path)}

    def _start_celery(self) -> dict[str, Any]:
        python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"celery-{int(time.time())}.log"
        log_handle = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            [
                python,
                "-m",
                "celery",
                "-A",
                "core.workflow.workers.celery_app:celery_app",
                "worker",
                "-l",
                "info",
                "-Q",
                "workflow",
                "-c",
                "2",
            ],
            cwd=str(BASE_DIR),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "PYTHONPATH": str(BASE_DIR)},
        )
        pids = _load_pids()
        pids["celery"] = {
            "pid": proc.pid,
            "started_at": _utc_now(),
            "log_file": str(log_path),
        }
        _save_pids(pids)
        return {"status": "started", "pid": proc.pid, "log_file": str(log_path)}

    def _stop_process(self, service_id: str) -> dict[str, Any]:
        pids = _load_pids()
        meta = pids.get(service_id)
        if not meta or not meta.get("pid"):
            return {"status": "stopped", "message": "nenhum processo registrado"}
        pid = int(meta["pid"])
        if _pid_alive(pid):
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            time.sleep(0.5)
            if _pid_alive(pid):
                os.killpg(os.getpgid(pid), signal.SIGKILL)
        pids.pop(service_id, None)
        _save_pids(pids)
        return {"status": "stopped", "pid": pid}

    def _stop_docker_service(self, container: str, service_id: str) -> dict[str, Any]:
        proc = subprocess.run(
            ["docker", "stop", container],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "docker stop falhou")
        pids = _load_pids()
        pids.pop(service_id, None)
        _save_pids(pids)
        return {"status": "stopped", "container": container}

    def _run_db_init(self) -> None:
        python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
        proc = subprocess.run(
            [python, "scripts/init_db.py"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHONPATH": str(BASE_DIR)},
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "db-init falhou")

    def read_log_tail(self, service_id: str, lines: int = 80) -> str:
        pids = _load_pids()
        meta = pids.get(service_id) or {}
        log_file = meta.get("log_file")
        if not log_file or not Path(log_file).exists():
            return ""
        content = Path(log_file).read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-lines:])
