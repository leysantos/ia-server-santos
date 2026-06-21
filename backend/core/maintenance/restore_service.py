"""Restauração de backups por stamp (app, database, knowledge, faiss)."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config.settings import BASE_DIR, FAISS_INDEX_DIR, KNOWLEDGE_DIR, get_settings
from core.maintenance.backup_service import is_wsl, wsl_to_win_path
from core.maintenance.config_store import MaintenanceConfig, load_config
from core.maintenance.retention import collect_stamps

logger = logging.getLogger(__name__)

REPO_ROOT = BASE_DIR.parent
STAMP_RE = re.compile(r"^\d{8}-\d{6}$")

ARTIFACT_FILES: dict[str, str] = {
    "app": "ia-server-santos-app-{stamp}.tar.gz",
    "database": "postgres-{stamp}.sql.gz",
    "knowledge": "knowledge-{stamp}.tar.gz",
    "faiss": "faiss-index-{stamp}.tar.gz",
    "config": "maintenance-config-{stamp}.json",
}

ARTIFACT_FOLDER: dict[str, str] = {
    "app": "app",
    "database": "database",
    "knowledge": "knowledge",
    "faiss": "faiss",
    "config": "config",
}

ALLOWED_TARGETS = frozenset(ARTIFACT_FILES.keys())
DEFAULT_RESTORE_TARGETS = ("database", "knowledge", "faiss")

ProgressCallback = Callable[[dict[str, Any]], None]


class MaintenanceRestoreService:
    def __init__(self, config: MaintenanceConfig | None = None) -> None:
        self.config = config or load_config()

    def _staging_root(self) -> Path:
        return self.config.resolved_staging_root()

    def list_stamps(self, *, include_drive: bool = True) -> list[str]:
        stamps = set(collect_stamps(self._staging_root()))
        if include_drive:
            stamps.update(self._collect_drive_stamps())
        return sorted(stamps, reverse=True)

    def inspect_stamp(self, stamp: str, *, from_drive: bool = True) -> dict[str, Any]:
        self._validate_stamp(stamp)
        artifacts: dict[str, Any] = {}
        missing: list[str] = []
        for target in sorted(ALLOWED_TARGETS):
            try:
                path = self.resolve_artifact(stamp, target, from_drive=from_drive)
                artifacts[target] = {
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "source": "staging" if str(self._staging_root()) in str(path) else "local",
                }
            except FileNotFoundError:
                missing.append(target)
        manifest = self._staging_root() / "logs" / f"manifest-{stamp}.json"
        manifest_drive = from_drive and self._manifest_on_drive(stamp)
        return {
            "stamp": stamp,
            "artifacts": artifacts,
            "missing": missing,
            "manifest_local": str(manifest) if manifest.exists() else None,
            "manifest_drive": manifest_drive,
            "restorable": bool(artifacts),
        }

    def run_restore(
        self,
        stamp: str,
        targets: list[str] | None = None,
        *,
        from_drive: bool = True,
        dry_run: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        self._validate_stamp(stamp)
        selected = [t for t in (targets or list(DEFAULT_RESTORE_TARGETS)) if t in ALLOWED_TARGETS]
        if not selected:
            raise ValueError(f"Informe ao menos um alvo: {', '.join(sorted(ALLOWED_TARGETS))}")

        result: dict[str, Any] = {
            "stamp": stamp,
            "targets": selected,
            "dry_run": dry_run,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "errors": [],
        }

        total = len(selected)

        def emit(phase: str, message: str, current: int) -> None:
            if on_progress:
                on_progress(
                    {
                        "phase": phase,
                        "message": message,
                        "current": current,
                        "total": total,
                        "percent": min(100, round(current / max(total, 1) * 100)),
                    }
                )

        step = 0
        for target in selected:
            step += 1
            emit(target, f"Preparando restore de {target}", step)
            try:
                artifact = self.resolve_artifact(stamp, target, from_drive=from_drive)
                if dry_run:
                    result["steps"].append(
                        {"target": target, "action": "dry_run", "artifact": str(artifact)}
                    )
                    continue
                if target == "database":
                    result["steps"].append(self._restore_database(artifact))
                elif target == "knowledge":
                    result["steps"].append(self._restore_knowledge(artifact))
                elif target == "faiss":
                    result["steps"].append(self._restore_faiss(artifact))
                elif target == "app":
                    result["steps"].append(self._restore_app(artifact))
                elif target == "config":
                    result["steps"].append(self._restore_config(artifact))
            except Exception as exc:
                result["errors"].append({"target": target, "error": str(exc)})

        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        result["status"] = "error" if result["errors"] else "completed"
        return result

    def resolve_artifact(self, stamp: str, target: str, *, from_drive: bool = True) -> Path:
        self._validate_stamp(stamp)
        if target not in ARTIFACT_FILES:
            raise ValueError(f"Alvo inválido: {target}")

        folder = ARTIFACT_FOLDER[target]
        filename = ARTIFACT_FILES[target].format(stamp=stamp)
        local = self._staging_root() / folder / filename
        if local.is_file():
            return local

        if from_drive:
            fetched = self._fetch_from_drive(folder, filename)
            if fetched and fetched.is_file():
                return fetched

        raise FileNotFoundError(
            f"Artefato não encontrado: {folder}/{filename} (staging ou Drive)"
        )

    @staticmethod
    def _validate_stamp(stamp: str) -> None:
        if not STAMP_RE.match(stamp.strip()):
            raise ValueError("STAMP inválido — use YYYYMMDD-HHMMSS (ex.: 20260621-165953)")

    def _collect_drive_stamps(self) -> set[str]:
        drive = self.config.backup_drive_win.strip()
        if not drive or not is_wsl() or not shutil.which("powershell.exe"):
            return set()
        subs = ",".join(repr(f) for f in ARTIFACT_FOLDER.values())
        ps = f"""
$dst = '{drive.replace("'", "''")}'
if (-not (Test-Path $dst)) {{ exit 0 }}
$stamps = New-Object System.Collections.Generic.HashSet[string]
@({subs}) | ForEach-Object {{
  $p = Join-Path $dst $_
  if (Test-Path $p) {{
    Get-ChildItem $p -File | ForEach-Object {{
      if ($_.Name -match '(\\d{{8}}-\\d{{6}})') {{ [void]$stamps.Add($Matches[1]) }}
    }}
  }}
}}
$stamps | ForEach-Object {{ Write-Output $_ }}
"""
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            return set()
        return {line.strip() for line in (proc.stdout or "").splitlines() if line.strip()}

    def _fetch_from_drive(self, folder: str, filename: str) -> Path | None:
        drive = self.config.backup_drive_win.strip()
        if not drive or not is_wsl() or not shutil.which("powershell.exe"):
            return None
        dest = self._staging_root() / folder / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        win_src = f"{drive}\\{folder}\\{filename}".replace("'", "''")
        win_dst = wsl_to_win_path(dest).replace("'", "''")
        ps = f"""
$src = '{win_src}'
$dst = '{win_dst}'
if (Test-Path $src) {{
  Copy-Item -Path $src -Destination $dst -Force
  Write-Output 'OK'
}}
"""
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode == 0 and "OK" in (proc.stdout or "") and dest.is_file():
            return dest
        return None

    def _manifest_on_drive(self, stamp: str) -> str | None:
        drive = self.config.backup_drive_win.strip()
        if not drive or not is_wsl() or not shutil.which("powershell.exe"):
            return None
        name = f"manifest-{stamp}.json"
        ps = f"if (Test-Path '{drive}\\logs\\{name}') {{ Write-Output 'yes' }}"
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if (proc.stdout or "").strip().lower() == "yes":
            return f"{drive}\\logs\\{name}"
        return None

    def _restore_database(self, artifact: Path) -> dict[str, Any]:
        settings = get_settings()
        container = self._postgres_container()
        if not container:
            raise RuntimeError("PostgreSQL indisponível — rode make docker-up")

        env = os.environ.copy()
        env["PGPASSWORD"] = settings.db_password

        commands = [
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{settings.db_name}' AND pid <> pg_backend_pid();",
            f"DROP DATABASE IF EXISTS {settings.db_name};",
            f"CREATE DATABASE {settings.db_name};",
        ]
        for sql in commands:
            proc = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-e",
                    f"PGPASSWORD={settings.db_password}",
                    container,
                    "psql",
                    "-U",
                    settings.db_user,
                    "-d",
                    "postgres",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    sql,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr or proc.stdout or "Falha ao recriar banco")

        with subprocess.Popen(["gzip", "-dc", str(artifact)], stdout=subprocess.PIPE) as gz:
            restore = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    "-e",
                    f"PGPASSWORD={settings.db_password}",
                    container,
                    "psql",
                    "-U",
                    settings.db_user,
                    "-d",
                    settings.db_name,
                    "-v",
                    "ON_ERROR_STOP=1",
                ],
                stdin=gz.stdout,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if gz.stdout:
                gz.stdout.close()
            gz.wait()

        if restore.returncode != 0:
            raise RuntimeError(restore.stderr or restore.stdout or "Restore SQL falhou")

        return {"target": "database", "action": "restored", "artifact": str(artifact)}

    def _restore_knowledge(self, artifact: Path) -> dict[str, Any]:
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        docs_dir = KNOWLEDGE_DIR / "raw" / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)

        restored: list[str] = []
        with tempfile.TemporaryDirectory(prefix="ia-restore-knowledge-") as tmp:
            tmp_path = Path(tmp)
            with tarfile.open(artifact, "r:gz") as tar:
                tar.extractall(tmp_path)

            catalog_src = tmp_path / "catalog.jsonl"
            if catalog_src.is_file():
                shutil.copy2(catalog_src, KNOWLEDGE_DIR / "catalog.jsonl")
                restored.append("catalog.jsonl")

            sidecars = tmp_path / "sidecars"
            if sidecars.is_dir():
                for sidecar in sidecars.glob("*.knowledge.json"):
                    shutil.copy2(sidecar, docs_dir / sidecar.name)
                    restored.append(f"sidecars/{sidecar.name}")

            documents = tmp_path / "documents"
            if documents.is_dir():
                for item in documents.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(documents)
                        dest = docs_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)
                        restored.append(f"documents/{rel}")

        return {
            "target": "knowledge",
            "action": "restored",
            "artifact": str(artifact),
            "files": restored[:20],
            "files_count": len(restored),
        }

    def _restore_faiss(self, artifact: Path) -> dict[str, Any]:
        backup_dir = FAISS_INDEX_DIR.parent / f"faiss_index.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if FAISS_INDEX_DIR.exists():
            shutil.move(str(FAISS_INDEX_DIR), str(backup_dir))

        FAISS_INDEX_DIR.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ia-restore-faiss-") as tmp:
            tmp_path = Path(tmp)
            with tarfile.open(artifact, "r:gz") as tar:
                tar.extractall(tmp_path)
            extracted = tmp_path / "faiss_index"
            if not extracted.is_dir():
                raise FileNotFoundError("Pacote FAISS sem pasta faiss_index/")
            shutil.copytree(extracted, FAISS_INDEX_DIR)

        return {
            "target": "faiss",
            "action": "restored",
            "artifact": str(artifact),
            "previous_backup": str(backup_dir) if backup_dir.exists() else None,
        }

    def _restore_app(self, artifact: Path) -> dict[str, Any]:
        with tarfile.open(artifact, "r:gz") as tar:
            tar.extractall(REPO_ROOT)
        return {
            "target": "app",
            "action": "restored",
            "artifact": str(artifact),
            "destination": str(REPO_ROOT),
            "note": "Rode make setup após restore app (.venv e node_modules não vêm no backup)",
        }

    def _restore_config(self, artifact: Path) -> dict[str, Any]:
        from core.maintenance.config_store import CONFIG_PATH, save_config

        data = json.loads(artifact.read_text(encoding="utf-8"))
        for key in ("wsl_backup_dir", "wsl_script_path", "wsl_schedule_note"):
            data.pop(key, None)
        config = MaintenanceConfig.model_validate(data)
        save_config(config)
        return {"target": "config", "action": "restored", "path": str(CONFIG_PATH)}

    @staticmethod
    def _postgres_container() -> str | None:
        if not shutil.which("docker"):
            return None
        proc = subprocess.run(
            ["docker", "ps", "--filter", "name=ia_server_santos_db", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        names = [n.strip() for n in (proc.stdout or "").splitlines() if n.strip()]
        return names[0] if names else None
