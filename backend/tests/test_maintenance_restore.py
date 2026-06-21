"""Testes de restore de backup."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from core.maintenance.restore_service import MaintenanceRestoreService


@pytest.fixture
def restore_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from core.maintenance.config_store import MaintenanceConfig

    cfg = MaintenanceConfig(backup_staging_dir=str(tmp_path))
    monkeypatch.setattr("core.maintenance.restore_service.load_config", lambda: cfg)
    return tmp_path


def test_validate_stamp_rejects_invalid():
    svc = MaintenanceRestoreService()
    with pytest.raises(ValueError, match="STAMP inválido"):
        svc._validate_stamp("not-a-stamp")


def test_resolve_artifact_from_staging(restore_root: Path):
    stamp = "20260621-120000"
    db_dir = restore_root / "database"
    db_dir.mkdir(parents=True)
    artifact = db_dir / f"postgres-{stamp}.sql.gz"
    with gzip.open(artifact, "wb") as gz:
        gz.write(b"-- empty\n")

    svc = MaintenanceRestoreService()
    found = svc.resolve_artifact(stamp, "database", from_drive=False)
    assert found == artifact
