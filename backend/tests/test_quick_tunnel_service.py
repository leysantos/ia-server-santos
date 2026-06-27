"""Testes do Quick Tunnel (trycloudflare)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from core.system import quick_tunnel_service as qts


@pytest.fixture
def qt_paths(tmp_path, monkeypatch):
    state = tmp_path / "quick_tunnel_state.json"
    api_log = tmp_path / "cloudflared-api.log"
    fe_log = tmp_path / "cloudflared-frontend.log"
    network_path = tmp_path / "network_access.json"

    monkeypatch.setattr(qts, "STATE_PATH", state)
    monkeypatch.setattr(qts, "API_LOG", api_log)
    monkeypatch.setattr(qts, "FE_LOG", fe_log)
    monkeypatch.setattr(qts, "SYSTEM_DIR", tmp_path)
    monkeypatch.setattr(
        "core.system.network_access_store.NETWORK_ACCESS_PATH",
        network_path,
    )
    return {"state": state, "api_log": api_log, "fe_log": fe_log}


def test_quick_tunnel_status_stopped_when_no_state(qt_paths, monkeypatch):
    monkeypatch.setattr(qts, "cloudflared_installed", lambda: True)
    status = qts.quick_tunnel_status()
    assert status["running"] is False
    assert status["status"] == "stopped"


def test_quick_tunnel_status_running_when_pids_alive(qt_paths, monkeypatch):
    monkeypatch.setattr(qts, "cloudflared_installed", lambda: True)
    qt_paths["state"].write_text(
        json.dumps(
            {
                "status": "running",
                "api_url": "https://api-demo.trycloudflare.com",
                "frontend_url": "https://fe-demo.trycloudflare.com",
                "api_pid": 111,
                "frontend_pid": 222,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qts, "_pid_alive", lambda pid: pid in (111, 222))
    status = qts.quick_tunnel_status()
    assert status["running"] is True
    assert status["api_url"] == "https://api-demo.trycloudflare.com"


def test_start_quick_tunnel_raises_without_cloudflared(qt_paths, monkeypatch):
    monkeypatch.setattr(qts, "cloudflared_installed", lambda: False)
    with pytest.raises(RuntimeError, match="cloudflared"):
        qts.start_quick_tunnel()


def test_start_quick_tunnel_success(qt_paths, monkeypatch):
    monkeypatch.setattr(qts, "cloudflared_installed", lambda: True)
    monkeypatch.setattr(qts, "_kill_quick_tunnels", lambda: None)
    monkeypatch.setattr(qts, "_pid_alive", lambda _pid: True)

    def fake_extract(log_path, timeout_sec=35):
        if "api" in log_path.name:
            return "https://api-test.trycloudflare.com"
        return "https://fe-test.trycloudflare.com"

    monkeypatch.setattr(qts, "_extract_url_from_log", fake_extract)

    proc = MagicMock()
    proc.pid = 9001
    monkeypatch.setattr(qts.subprocess, "Popen", lambda *a, **k: proc)

    result = qts.start_quick_tunnel()
    assert result["running"] is True
    assert result["api_url"] == "https://api-test.trycloudflare.com"
    assert result["frontend_url"] == "https://fe-test.trycloudflare.com"
    saved = json.loads(qt_paths["state"].read_text(encoding="utf-8"))
    assert saved["status"] == "running"


def test_stop_quick_tunnel_clears_state(qt_paths, monkeypatch):
    monkeypatch.setattr(qts, "cloudflared_installed", lambda: True)
    qt_paths["state"].write_text(
        json.dumps(
            {
                "status": "running",
                "api_url": "https://api-demo.trycloudflare.com",
                "frontend_url": "https://fe-demo.trycloudflare.com",
                "api_pid": 111,
                "frontend_pid": 222,
            }
        ),
        encoding="utf-8",
    )
    killed = {"called": False}
    monkeypatch.setattr(qts, "_kill_quick_tunnels", lambda: killed.update({"called": True}))
    monkeypatch.setattr(qts, "_pid_alive", lambda _pid: False)

    result = qts.stop_quick_tunnel()
    assert killed["called"] is True
    assert result["running"] is False
    saved = json.loads(qt_paths["state"].read_text(encoding="utf-8"))
    assert saved["status"] == "stopped"
