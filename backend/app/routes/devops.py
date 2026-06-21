"""Rotas para controle de serviços locais e console shell (dev)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.devops import (
    DevServiceActionResponse,
    DevServicesResponse,
    DevStackStartResponse,
    ShellHistoryResponse,
    ShellRunRequest,
    ShellRunResponse,
)
from core.devops.process_manager import ProcessManager, REPO_ROOT
from core.devops.shell_runner import list_shell_history, run_shell

router = APIRouter(prefix="/devops", tags=["DevOps"])

_manager = ProcessManager()

HINTS = {
    "api": "Inicie manualmente no terminal: make api",
    "frontend": "Opcional: npm run dev em frontend/ ou use o botão Iniciar",
    "ollama": "Instale e inicie o Ollama fora da aplicação (systemd ou ollama serve)",
}


@router.get("/services", response_model=DevServicesResponse)
def list_services():
    return DevServicesResponse(
        services=_manager.list_services(),
        repo_root=str(REPO_ROOT),
        hints=HINTS,
    )


@router.post("/services/{service_id}/start", response_model=DevServiceActionResponse)
def start_service(service_id: str):
    try:
        result = _manager.start_service(service_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return DevServiceActionResponse(
        id=service_id,
        status=result.get("status", "started"),
        message=result.get("message", ""),
        pid=result.get("pid"),
        log_file=result.get("log_file"),
        services=_manager.list_services(),
    )


@router.post("/services/{service_id}/stop", response_model=DevServiceActionResponse)
def stop_service(service_id: str):
    try:
        result = _manager.stop_service(service_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return DevServiceActionResponse(
        id=service_id,
        status=result.get("status", "stopped"),
        message=result.get("message", ""),
        pid=result.get("pid"),
        services=_manager.list_services(),
    )


@router.get("/services/{service_id}/logs")
def service_logs(service_id: str, lines: int = 80):
    text = _manager.read_log_tail(service_id, lines=min(lines, 500))
    return {"service_id": service_id, "lines": lines, "log": text}


@router.post("/stack/start-core", response_model=DevStackStartResponse)
def start_core_stack():
    """Sobe PostgreSQL (+ db-init). API e frontend permanecem manuais."""
    payload = _manager.start_core_stack()
    return DevStackStartResponse(**payload)


@router.post("/shell/run", response_model=ShellRunResponse)
def shell_run(body: ShellRunRequest):
    try:
        return run_shell(body.command, cwd=body.cwd, timeout_sec=body.timeout_sec)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError:
        raise HTTPException(status_code=408, detail="Comando excedeu o tempo limite") from None


@router.get("/shell/history", response_model=ShellHistoryResponse)
def shell_history(limit: int = 30):
    return ShellHistoryResponse(items=list_shell_history(limit=min(limit, 100)))
