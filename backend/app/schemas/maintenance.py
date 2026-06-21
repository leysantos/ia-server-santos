"""Schemas da API de manutenção/backup."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MaintenanceConfigUpdate(BaseModel):
    backup_drive_win: str | None = None
    backup_staging_dir: str | None = None
    keep_latest_sets: int | None = Field(default=None, ge=1, le=10)
    include_knowledge_pdfs: bool | None = None
    include_faiss: bool | None = None
    include_database: bool | None = None


class MaintenanceConfigResponse(BaseModel):
    backup_drive_win: str
    backup_staging_dir: str
    keep_latest_sets: int = 1
    include_knowledge_pdfs: bool
    include_faiss: bool
    include_database: bool
    backup_staging_exists: bool = False
    backup_drive_exists: bool = False
    subfolders: dict[str, bool] = Field(default_factory=dict)
    config_path: str = ""


class MaintenanceBackupRequest(BaseModel):
    targets: list[str] = Field(
        default_factory=lambda: ["app", "database", "knowledge", "faiss"],
        description="app | database | knowledge | faiss | config",
    )


class MaintenanceRestoreRequest(BaseModel):
    stamp: str = Field(..., description="YYYYMMDD-HHMMSS")
    targets: list[str] = Field(
        default_factory=lambda: ["database", "knowledge", "faiss"],
        description="database | knowledge | faiss | app | config",
    )
    from_drive: bool = True
    dry_run: bool = False


class MaintenanceRestoreResponse(BaseModel):
    stamp: str
    targets: list[str]
    dry_run: bool
    started_at: str
    finished_at: str | None = None
    status: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class MaintenanceInitResponse(BaseModel):
    backup_staging_dir: str
    backup_drive_win: str
    created: list[str]
    subfolders: dict[str, bool]


class MaintenanceStatusResponse(BaseModel):
    environment: dict[str, Any]
    config: dict[str, Any]
    history: list[dict[str, Any]]


class MaintenanceBackupResponse(BaseModel):
    id: str
    status: str
    started_at: str
    finished_at: str | None = None
    targets: list[str]
    artifacts: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    retention: dict[str, Any] | None = None
    drive_sync: dict[str, Any] | None = None
