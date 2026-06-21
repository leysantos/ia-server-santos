"""Testes do módulo de manutenção/backup."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.maintenance.backup_service import MaintenanceBackupService, wsl_to_win_path
from core.maintenance.config_store import MaintenanceConfig, load_config, save_config
from core.maintenance.retention import apply_retention, collect_stamps, extract_stamp


@pytest.fixture
def backup_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "staging"
    cfg = MaintenanceConfig(
        backup_staging_dir=str(root),
        backup_drive_win=r"G:\Meu Drive\Backups_IA_Server",
        keep_latest_sets=1,
    )
    monkeypatch.setattr(
        "core.maintenance.backup_service.load_config",
        lambda: cfg,
    )
    monkeypatch.setattr(
        "core.maintenance.config_store.load_config",
        lambda: cfg,
    )
    return root


def test_wsl_to_win_path():
    assert wsl_to_win_path("/mnt/c/backup_wsl") == "C:\\backup_wsl"
    assert wsl_to_win_path("/mnt/d/Backups/test") == "D:\\Backups\\test"


def test_extract_stamp():
    assert extract_stamp("ia-server-santos-app-20260621-165953.tar.gz") == "20260621-165953"


def test_retention_keeps_latest_only(tmp_path: Path):
    root = tmp_path / "ret"
    for folder in ("app", "database"):
        (root / folder).mkdir(parents=True)
    (root / "app" / "ia-server-santos-app-20260621-100000.tar.gz").write_bytes(b"a")
    (root / "app" / "ia-server-santos-app-20260621-200000.tar.gz").write_bytes(b"b")
    (root / "database" / "postgres-20260621-100000.sql.gz").write_bytes(b"c")
    (root / "logs").mkdir()
    (root / "logs" / "manifest-20260621-100000.json").write_text("{}")
    (root / "logs" / "manifest-20260621-200000.json").write_text("{}")

    result = apply_retention(root, keep_latest=1)
    assert "20260621-200000" in result["kept_stamps"]
    assert not (root / "app" / "ia-server-santos-app-20260621-100000.tar.gz").exists()
    assert (root / "app" / "ia-server-santos-app-20260621-200000.tar.gz").exists()
    assert len(collect_stamps(root)) == 1


def test_init_folders_creates_structure(backup_root: Path):
    svc = MaintenanceBackupService()
    result = svc.init_folders()
    assert result["backup_staging_dir"] == str(backup_root)
    for name in ("app", "database", "knowledge", "faiss", "logs", "config"):
        assert (backup_root / name).is_dir()


def test_backup_app_creates_tar(backup_root: Path):
    svc = MaintenanceBackupService()
    svc.init_folders()
    manifest = svc.run_backup(["app"])
    assert manifest["status"] == "completed"
    assert len(manifest["artifacts"]) == 1
    path = Path(manifest["artifacts"][0]["path"])
    assert path.exists()


def test_save_and_load_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr("core.maintenance.config_store.CONFIG_PATH", cfg_path)
    original = MaintenanceConfig(keep_latest_sets=2)
    save_config(original)
    loaded = load_config()
    assert loaded.keep_latest_sets == 2
