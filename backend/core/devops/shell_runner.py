"""Execução segura de comandos shell (dev local)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import BASE_DIR

REPO_ROOT = BASE_DIR.parent
HISTORY_FILE = BASE_DIR / "data" / "devops" / "shell_history.jsonl"
MAX_OUTPUT_CHARS = 120_000
DEFAULT_TIMEOUT_SEC = 120
MAX_TIMEOUT_SEC = 300

BLOCKED_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\brm\s+-rf\s+/",
        r"\brm\s+-rf\s+~",
        r"\bmkfs\b",
        r"\bdd\s+if=",
        r">\s*/dev/sd",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bhalt\b",
        r"\bpoweroff\b",
        r"\:wsl\s+--unregister\b",
        r"\bchmod\s+-R\s+777\s+/",
        r"\bsudo\s+rm\b",
        r";\s*rm\s+-rf",
        r"\|\s*rm\s+-rf",
    )
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_cwd(requested: str | None) -> Path:
    if not requested:
        return REPO_ROOT.resolve()
    candidate = (REPO_ROOT / requested).resolve() if not requested.startswith("/") else Path(requested).resolve()
    repo = REPO_ROOT.resolve()
    if repo not in candidate.parents and candidate != repo:
        raise ValueError("cwd deve ficar dentro do repositório")
    if not candidate.is_dir():
        raise ValueError(f"Diretório inválido: {requested}")
    return candidate


def validate_command(command: str) -> None:
    text = command.strip()
    if not text:
        raise ValueError("Comando vazio")
    if len(text) > 4000:
        raise ValueError("Comando muito longo")
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(text):
            raise ValueError("Comando bloqueado por segurança")


def run_shell(
    command: str,
    *,
    cwd: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> dict[str, Any]:
    validate_command(command)
    workdir = _resolve_cwd(cwd)
    timeout = min(max(timeout_sec, 1), MAX_TIMEOUT_SEC)

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""), "LANG": "C.UTF-8"},
        )
    except subprocess.TimeoutExpired as exc:
        record = {
            "ts": _utc_now(),
            "command": command,
            "cwd": str(workdir),
            "exit_code": -1,
            "truncated": False,
        }
        _append_history(record)
        raise TimeoutError(f"Timeout após {timeout}s") from exc

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = stdout
    if stderr:
        combined = f"{stdout}\n{stderr}".strip() if stdout else stderr
    truncated = False
    if len(combined) > MAX_OUTPUT_CHARS:
        combined = combined[:MAX_OUTPUT_CHARS] + "\n… [saída truncada]"
        truncated = True

    record = {
        "ts": _utc_now(),
        "command": command,
        "cwd": str(workdir),
        "exit_code": proc.returncode,
        "truncated": truncated,
    }
    _append_history(record)

    return {
        **record,
        "output": combined,
        "success": proc.returncode == 0,
    }


def _append_history(record: dict[str, Any]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_shell_history(limit: int = 30) -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    items: list[dict[str, Any]] = []
    for line in reversed(lines[-limit:]):
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items
