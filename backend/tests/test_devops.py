"""Testes do módulo DevOps (shell e serviços)."""

from __future__ import annotations

import pytest

from core.devops.process_manager import ProcessManager
from core.devops.shell_runner import run_shell, validate_command


def test_validate_command_blocks_rm_rf():
    with pytest.raises(ValueError, match="bloqueado"):
        validate_command("rm -rf /")


def test_run_shell_echo(tmp_path, monkeypatch):
    monkeypatch.setattr("core.devops.shell_runner.REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        "core.devops.shell_runner.HISTORY_FILE",
        tmp_path / "data" / "devops" / "shell_history.jsonl",
    )
    result = run_shell("echo hello-devops")
    assert result["success"] is True
    assert "hello-devops" in result["output"]


def test_process_manager_list_services():
    mgr = ProcessManager()
    services = mgr.list_services()
    ids = {s["id"] for s in services}
    assert "postgres" in ids
    assert "api" in ids
    assert "frontend" in ids
    for svc in services:
        assert svc["status"] in ("running", "stopped", "unknown")
        assert "can_start" in svc
