"""Rotas de manutenção e backup."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.maintenance import (
    MaintenanceBackupRequest,
    MaintenanceBackupResponse,
    MaintenanceConfigResponse,
    MaintenanceConfigUpdate,
    MaintenanceInitResponse,
    MaintenanceRestoreRequest,
    MaintenanceRestoreResponse,
    MaintenanceStatusResponse,
)
from core.maintenance.backup_service import MaintenanceBackupService
from core.maintenance.config_store import config_to_public_dict, load_config, save_config
from core.maintenance.restore_service import MaintenanceRestoreService
from core.runtime.job_tracking import track_sync_job

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


@router.get("/status", response_model=MaintenanceStatusResponse)
def maintenance_status():
    return MaintenanceBackupService().status()


@router.get("/config", response_model=MaintenanceConfigResponse)
def get_maintenance_config():
    return config_to_public_dict(load_config())


@router.put("/config", response_model=MaintenanceConfigResponse)
def update_maintenance_config(body: MaintenanceConfigUpdate):
    current = load_config()
    data = current.model_dump()
    for key, value in body.model_dump(exclude_unset=True).items():
        data[key] = value
    updated = save_config(current.model_copy(update=data))
    return config_to_public_dict(updated)


@router.post("/init-folders", response_model=MaintenanceInitResponse)
def init_backup_folders():
    return MaintenanceBackupService().init_folders()


@router.get("/history")
def backup_history(limit: int = 20):
    return {"items": MaintenanceBackupService().list_history(limit=min(limit, 100))}


@router.post("/backup", response_model=MaintenanceBackupResponse)
def run_backup(body: MaintenanceBackupRequest):
    label_targets = ", ".join(body.targets)
    label = f"Backup — {label_targets}"

    with track_sync_job(kind="maintenance", label=label) as job:

        def on_progress(data: dict) -> None:
            job.update(
                phase=data.get("phase"),
                message=data.get("message"),
                current=int(data.get("current") or 0),
                total=int(data.get("total") or 0),
                percent=int(data.get("percent") or 0),
                log=True,
            )

        try:
            result = MaintenanceBackupService().run_backup(
                body.targets,
                on_progress=on_progress,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            job.finish(status="error", message=str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        status = result.get("status", "completed")
        if status == "completed":
            msg = f"Backup concluído — {len(result.get('artifacts', []))} artefato(s)"
        else:
            err_parts = [
                f"{e.get('target', '?')}: {e.get('error', '?')}"
                for e in result.get("errors", [])
            ]
            msg = f"Backup com erros — {len(result.get('errors', []))} falha(s)"
            if err_parts:
                msg += " (" + "; ".join(err_parts) + ")"
        job.finish(status=status, message=msg)
        return result


@router.get("/stamps")
def list_backup_stamps(include_drive: bool = True):
    return {"stamps": MaintenanceRestoreService().list_stamps(include_drive=include_drive)}


@router.get("/restore/{stamp}/inspect")
def inspect_restore_stamp(stamp: str, from_drive: bool = True):
    try:
        return MaintenanceRestoreService().inspect_stamp(stamp, from_drive=from_drive)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/restore", response_model=MaintenanceRestoreResponse)
def run_restore(body: MaintenanceRestoreRequest):
    label = f"Restore — {body.stamp} ({', '.join(body.targets)})"

    with track_sync_job(kind="maintenance", label=label) as job:

        def on_progress(data: dict) -> None:
            job.update(
                phase=data.get("phase"),
                message=data.get("message"),
                current=int(data.get("current") or 0),
                total=int(data.get("total") or 0),
                percent=int(data.get("percent") or 0),
                log=True,
            )

        try:
            result = MaintenanceRestoreService().run_restore(
                body.stamp,
                body.targets,
                from_drive=body.from_drive,
                dry_run=body.dry_run,
                on_progress=on_progress,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            job.finish(status="error", message=str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        status = result.get("status", "completed")
        job.finish(
            status=status,
            message=f"Restore {body.stamp} — {status}",
        )
        return result
