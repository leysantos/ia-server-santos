"""Configuração persistente de backup/manutenção (editável pela UI)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from config.settings import BASE_DIR

CONFIG_PATH = BASE_DIR / "data" / "maintenance" / "config.json"

# Google Drive (Windows) — destino final; WSL grava em staging e sincroniza via PowerShell.
DEFAULT_BACKUP_DRIVE_WIN = r"G:\Meu Drive\Backups_IA_Server"
DEFAULT_BACKUP_STAGING = "/mnt/c/Backups/.ia-server-staging"

BACKUP_SUBFOLDERS = ("app", "database", "knowledge", "faiss", "logs", "config")


class MaintenanceConfig(BaseModel):
    backup_drive_win: str = Field(
        default=DEFAULT_BACKUP_DRIVE_WIN,
        description="Pasta no Google Drive (caminho Windows)",
    )
    backup_staging_dir: str = Field(
        default=DEFAULT_BACKUP_STAGING,
        description="Staging local no WSL antes de enviar ao Drive",
    )
    keep_latest_sets: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Quantos conjuntos de backup manter (apaga os mais antigos)",
    )
    include_knowledge_pdfs: bool = Field(default=False)
    include_faiss: bool = Field(default=True)
    include_database: bool = Field(default=True)

    # Legado — migrado para backup_staging_dir / backup_drive_win
    backup_root: str | None = Field(default=None)

    def resolved_staging_root(self) -> Path:
        return Path(self.backup_staging_dir).expanduser()


def load_config() -> MaintenanceConfig:
    if not CONFIG_PATH.exists():
        return MaintenanceConfig()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        # Migração: backup_root antigo (/mnt/c/Backups/IA-Server-Santos) → staging + Drive
        if data.get("backup_root") and not data.get("backup_staging_dir"):
            legacy = data["backup_root"]
            if "IA-Server-Santos" in legacy or "Backups" in legacy:
                data.setdefault("backup_staging_dir", DEFAULT_BACKUP_STAGING)
                data.setdefault("backup_drive_win", DEFAULT_BACKUP_DRIVE_WIN)
            else:
                data.setdefault("backup_staging_dir", legacy)
        data.setdefault("keep_latest_sets", 1)
        data.setdefault("backup_drive_win", DEFAULT_BACKUP_DRIVE_WIN)
        data.setdefault("backup_staging_dir", DEFAULT_BACKUP_STAGING)
        for legacy_key in ("wsl_backup_dir", "wsl_script_path", "wsl_schedule_note"):
            data.pop(legacy_key, None)
        return MaintenanceConfig.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return MaintenanceConfig()


def save_config(config: MaintenanceConfig) -> MaintenanceConfig:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(exclude={"backup_root"})
    CONFIG_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return config


def config_to_public_dict(config: MaintenanceConfig) -> dict[str, Any]:
    staging = config.resolved_staging_root()
    drive_win = config.backup_drive_win
    drive_ok = False
    if is_wsl():
        try:
            import subprocess

            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"Test-Path '{drive_win.replace(chr(39), chr(39)+chr(39))}'",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            drive_ok = proc.stdout.strip().lower() == "true"
        except Exception:
            drive_ok = False
    return {
        **config.model_dump(exclude={"backup_root"}),
        "backup_staging_exists": staging.exists(),
        "backup_drive_exists": drive_ok,
        "subfolders": {name: (staging / name).exists() for name in BACKUP_SUBFOLDERS},
        "config_path": str(CONFIG_PATH),
    }


def is_wsl() -> bool:
    import platform

    try:
        return "microsoft" in platform.uname().release.lower()
    except Exception:
        return False
