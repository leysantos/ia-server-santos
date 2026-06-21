"""Orquestra backups da aplicação, banco, knowledge e WSL."""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config.settings import BASE_DIR, FAISS_INDEX_DIR, KNOWLEDGE_DIR, get_settings
from core.maintenance.config_store import (
    BACKUP_SUBFOLDERS,
    MaintenanceConfig,
    load_config,
)
from core.maintenance.retention import apply_retention

logger = logging.getLogger(__name__)

REPO_ROOT = BASE_DIR.parent

APP_TAR_EXCLUDES = {
    ".git",
    "node_modules",
    ".next",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".turbo",
    "coverage",
    ".coverage",
    "htmlcov",
    ".netlify",
}

APP_TOP_LEVEL = (
    "frontend",
    "backend",
    "docs",
    "infra",
    "scripts",
    "Makefile",
    "pyproject.toml",
    "README.md",
    ".cursor",
    ".env.example",
)

ProgressCallback = Callable[[dict[str, Any]], None]


def is_wsl() -> bool:
    try:
        return "microsoft" in platform.uname().release.lower()
    except Exception:
        return False


def wsl_to_win_path(path: Path | str) -> str:
    text = str(Path(path).resolve())
    if text.startswith("/mnt/") and len(text) >= 7:
        drive = text[5].upper()
        rest = text[6:].lstrip("/").replace("/", "\\")
        return f"{drive}:\\{rest}" if rest else f"{drive}:\\"
    return text.replace("/", "\\")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


class MaintenanceBackupService:
    def __init__(self, config: MaintenanceConfig | None = None) -> None:
        self.config = config or load_config()

    def _write_root(self) -> Path:
        return self.config.resolved_staging_root()

    def status(self) -> dict[str, Any]:
        root = self._write_root()
        return {
            "environment": {
                "is_wsl": is_wsl(),
                "repo_root": str(REPO_ROOT),
                "platform": platform.platform(),
            },
            "config": {
                "backup_staging_dir": str(root),
                "backup_drive_win": self.config.backup_drive_win,
                "keep_latest_sets": self.config.keep_latest_sets,
                "include_knowledge_pdfs": self.config.include_knowledge_pdfs,
                "include_faiss": self.config.include_faiss,
                "include_database": self.config.include_database,
                "subfolders": {name: (root / name).exists() for name in BACKUP_SUBFOLDERS},
            },
            "history": self.list_history(limit=10),
        }

    def init_folders(self) -> dict[str, Any]:
        root = self._write_root()
        created: list[str] = []
        for name in BACKUP_SUBFOLDERS:
            folder = root / name
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True)
                created.append(str(folder))
        created.extend(self._ensure_drive_folders())
        readme = root / "README.txt"
        if not readme.exists():
            readme.write_text(
                "Backups IA Server Santos (staging local → Google Drive)\n"
                f"Criado em {datetime.now(timezone.utc).isoformat()}\n\n"
                f"Drive: {self.config.backup_drive_win}\n"
                f"Retenção: {self.config.keep_latest_sets} conjunto(s) mais recente(s)\n\n"
                "Pastas:\n"
                "  app/       — snapshot frontend + backend + docs + infra\n"
                "  database/  — dumps PostgreSQL\n"
                "  knowledge/ — catálogo e metadados\n"
                "  faiss/     — índices vetoriais\n"
                "  logs/      — manifestos JSON\n"
                "  config/    — config exportada\n",
                encoding="utf-8",
            )
            created.append(str(readme))
        return {
            "backup_staging_dir": str(root),
            "backup_drive_win": self.config.backup_drive_win,
            "created": created,
            "subfolders": {name: (root / name).exists() for name in BACKUP_SUBFOLDERS},
        }

    def _ensure_drive_folders(self) -> list[str]:
        drive = self.config.backup_drive_win.strip()
        if not drive or not is_wsl() or not shutil.which("powershell.exe"):
            return []
        subs = ",".join(repr(s) for s in BACKUP_SUBFOLDERS)
        ps = f"""
$dst = '{drive.replace("'", "''")}'
if (-not (Test-Path $dst)) {{ New-Item -ItemType Directory -Path $dst -Force | Out-Null }}
@({subs}) | ForEach-Object {{
  $p = Join-Path $dst $_
  if (-not (Test-Path $p)) {{ New-Item -ItemType Directory -Path $p -Force | Out-Null }}
}}
"""
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            timeout=60,
        )
        return [drive]

    def list_history(self, *, limit: int = 20) -> list[dict[str, Any]]:
        logs_dir = self._write_root() / "logs"
        if not logs_dir.exists():
            return []
        manifests = sorted(logs_dir.glob("manifest-*.json"), reverse=True)
        items: list[dict[str, Any]] = []
        for path in manifests[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["manifest_file"] = path.name
                items.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return items

    def run_backup(
        self,
        targets: list[str],
        *,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        allowed = {"app", "database", "knowledge", "faiss", "config"}
        selected = [t for t in targets if t in allowed]
        if not selected:
            raise ValueError(f"Informe ao menos um alvo: {', '.join(sorted(allowed))}")

        self.init_folders()
        stamp = _timestamp()
        manifest: dict[str, Any] = {
            "id": stamp,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "targets": selected,
            "artifacts": [],
            "errors": [],
        }

        total = len(selected)

        def emit(phase: str, message: str, current: int) -> None:
            if not on_progress:
                return
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
        if "config" in selected:
            step += 1
            emit("config", "Exportando configuração de manutenção", step)
            manifest["artifacts"].append(self._backup_config(stamp))

        if "app" in selected:
            step += 1
            emit("app", "Compactando frontend, backend e arquivos complementares", step)
            try:
                manifest["artifacts"].append(self._backup_app(stamp))
            except Exception as exc:
                manifest["errors"].append({"target": "app", "error": str(exc)})

        if "database" in selected and self.config.include_database:
            step += 1
            emit("database", "Gerando dump PostgreSQL", step)
            try:
                manifest["artifacts"].append(self._backup_database(stamp))
            except Exception as exc:
                manifest["errors"].append({"target": "database", "error": str(exc)})

        if "knowledge" in selected:
            step += 1
            emit("knowledge", "Compactando catálogo e metadados", step)
            try:
                manifest["artifacts"].append(self._backup_knowledge(stamp))
            except Exception as exc:
                manifest["errors"].append({"target": "knowledge", "error": str(exc)})

        if "faiss" in selected and self.config.include_faiss:
            step += 1
            emit("faiss", "Compactando índices FAISS", step)
            try:
                manifest["artifacts"].append(self._backup_faiss(stamp))
            except Exception as exc:
                manifest["errors"].append({"target": "faiss", "error": str(exc)})

        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        manifest["status"] = "error" if manifest["errors"] else "completed"

        try:
            manifest["retention"] = apply_retention(
                self._write_root(),
                keep_latest=self.config.keep_latest_sets,
            )
        except Exception as exc:
            manifest["errors"].append({"target": "retention", "error": str(exc)})
            manifest["status"] = "error"

        self._write_manifest(stamp, manifest)

        try:
            manifest["drive_sync"] = self._sync_to_google_drive()
            self._apply_retention_on_drive()
        except Exception as exc:
            manifest["errors"].append({"target": "drive_sync", "error": str(exc)})
            if manifest["artifacts"]:
                manifest["status"] = "error"
            self._write_manifest(stamp, manifest)

        return manifest

    def _sync_to_google_drive(self) -> dict[str, Any]:
        drive = self.config.backup_drive_win.strip()
        staging = self._write_root()
        if not drive:
            return {"skipped": True, "reason": "backup_drive_win não configurado"}
        if not is_wsl() or not shutil.which("powershell.exe"):
            return {"skipped": True, "reason": "PowerShell/WSL indisponível"}
        win_src = wsl_to_win_path(staging)
        win_dst = drive.replace("'", "''")
        ps = f"""
$src = '{win_src.replace("'", "''")}'
$dst = '{win_dst}'
if (-not (Test-Path $dst)) {{ New-Item -ItemType Directory -Path $dst -Force | Out-Null }}
@('app','database','knowledge','faiss','logs','config') | ForEach-Object {{
  $from = Join-Path $src $_
  $to = Join-Path $dst $_
  if (Test-Path $from) {{
    if (-not (Test-Path $to)) {{ New-Item -ItemType Directory -Path $to -Force | Out-Null }}
    Get-ChildItem $from -File | ForEach-Object {{ Copy-Item $_.FullName -Destination $to -Force }}
  }}
}}
Write-Output 'OK'
"""
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=900,
        )
        if proc.returncode != 0 or "OK" not in (proc.stdout or ""):
            err = (proc.stderr or proc.stdout or "sync falhou")[:500]
            raise RuntimeError(err)
        return {"destination": drive, "source": str(staging), "status": "ok"}

    def _apply_retention_on_drive(self) -> None:
        drive = self.config.backup_drive_win.strip()
        keep = self.config.keep_latest_sets
        if not drive or not is_wsl() or not shutil.which("powershell.exe"):
            return
        win_dst = drive.replace("'", "''")
        ps = f"""
$root = '{win_dst}'
$keep = {keep}
$stamps = @()
Get-ChildItem (Join-Path $root 'app') -File -ErrorAction SilentlyContinue | ForEach-Object {{
  if ($_.Name -match '(\\d{{8}}-\\d{{6}})') {{ $stamps += $matches[1] }}
}}
$unique = $stamps | Select-Object -Unique | Sort-Object -Descending
$toRemove = $unique | Select-Object -Skip $keep
foreach ($s in $toRemove) {{
  @('app','database','knowledge','faiss','config') | ForEach-Object {{
    Get-ChildItem (Join-Path $root $_) -Filter \"*$s*\" -File -ErrorAction SilentlyContinue | Remove-Item -Force
  }}
  Remove-Item (Join-Path $root \"logs\\manifest-$s.json\") -Force -ErrorAction SilentlyContinue
}}
Write-Output ('removed:' + ($toRemove -join ','))
"""
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            timeout=120,
        )

    def _write_manifest(self, stamp: str, manifest: dict[str, Any]) -> Path:
        path = self._write_root() / "logs" / f"manifest-{stamp}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _backup_config(self, stamp: str) -> dict[str, Any]:
        dest = self._write_root() / "config" / f"maintenance-config-{stamp}.json"
        dest.write_text(
            json.dumps(self.config.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self._artifact("config", dest)

    def _backup_app(self, stamp: str) -> dict[str, Any]:
        dest = self._write_root() / "app" / f"ia-server-santos-app-{stamp}.tar.gz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(dest, "w:gz") as tar:
            for rel in APP_TOP_LEVEL:
                src = REPO_ROOT / rel
                if not src.exists():
                    continue
                tar.add(src, arcname=rel, filter=self._tar_filter)
        return self._artifact("app", dest)

    @staticmethod
    def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        rel = info.name
        parts = Path(rel).parts
        if any(part in APP_TAR_EXCLUDES for part in parts):
            return None
        if any(part.endswith(".pyc") for part in parts):
            return None
        return info

    def _backup_database(self, stamp: str) -> dict[str, Any]:
        dest = self._write_root() / "database" / f"postgres-{stamp}.sql.gz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        settings = get_settings()
        dump_bytes = self._run_pg_dump(settings)
        with subprocess.Popen(["gzip", "-c"], stdin=subprocess.PIPE, stdout=open(dest, "wb")) as gz:
            assert gz.stdin is not None
            gz.stdin.write(dump_bytes)
            gz.stdin.close()
            code = gz.wait()
            if code != 0:
                raise RuntimeError("gzip falhou ao compactar dump")
        return self._artifact("database", dest)

    def _run_pg_dump(self, settings) -> bytes:
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.db_password
        if shutil.which("pg_dump"):
            proc = subprocess.run(
                [
                    "pg_dump",
                    "-h",
                    settings.db_host,
                    "-p",
                    str(settings.db_port),
                    "-U",
                    settings.db_user,
                    "-d",
                    settings.db_name,
                ],
                check=False,
                capture_output=True,
                env=env,
            )
            if proc.returncode == 0:
                return proc.stdout
            stderr = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"pg_dump falhou: {stderr[:500]}")

        if shutil.which("docker"):
            proc = subprocess.run(
                ["docker", "ps", "--filter", "name=ia_server_santos_db", "--format", "{{.Names}}"],
                check=False,
                capture_output=True,
                text=True,
            )
            container = (proc.stdout or "").strip().splitlines()
            if container and container[0]:
                dproc = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "-e",
                        f"PGPASSWORD={settings.db_password}",
                        container[0],
                        "pg_dump",
                        "-U",
                        settings.db_user,
                        "-d",
                        settings.db_name,
                    ],
                    check=False,
                    capture_output=True,
                )
                if dproc.returncode == 0:
                    return dproc.stdout
                stderr = dproc.stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"pg_dump via Docker falhou: {stderr[:500]}")

        raise RuntimeError(
            "pg_dump não encontrado no WSL e container ia_server_santos_db indisponível. "
            "Instale postgresql-client ou suba o Postgres: make docker-up"
        )

    def _backup_knowledge(self, stamp: str) -> dict[str, Any]:
        dest = self._write_root() / "knowledge" / f"knowledge-{stamp}.tar.gz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(dest, "w:gz") as tar:
            catalog = KNOWLEDGE_DIR / "catalog.jsonl"
            if catalog.exists():
                tar.add(catalog, arcname="catalog.jsonl")
            for sidecar in (KNOWLEDGE_DIR / "raw" / "documents").glob("*.knowledge.json"):
                tar.add(sidecar, arcname=f"sidecars/{sidecar.name}")
            if self.config.include_knowledge_pdfs:
                docs = KNOWLEDGE_DIR / "raw" / "documents"
                if docs.exists():
                    tar.add(docs, arcname="documents", filter=self._tar_filter)
        return self._artifact("knowledge", dest)

    def _backup_faiss(self, stamp: str) -> dict[str, Any]:
        dest = self._write_root() / "faiss" / f"faiss-index-{stamp}.tar.gz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not FAISS_INDEX_DIR.exists():
            raise FileNotFoundError(f"Índice FAISS não encontrado: {FAISS_INDEX_DIR}")
        with tarfile.open(dest, "w:gz") as tar:
            tar.add(FAISS_INDEX_DIR, arcname="faiss_index")
        return self._artifact("faiss", dest)

    @staticmethod
    def _artifact(target: str, path: Path) -> dict[str, Any]:
        size = path.stat().st_size if path.exists() else 0
        return {
            "target": target,
            "path": str(path),
            "size_bytes": size,
            "size_human": _human_size(size),
        }
