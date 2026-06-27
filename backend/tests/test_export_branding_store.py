"""Personalização global de exportação."""

from __future__ import annotations

import json

import pytest

from core.system.export_branding_store import (
    BRANDING_PATH,
    get_global_export_branding,
    save_global_export_branding,
)


@pytest.fixture
def branding_path(tmp_path, monkeypatch):
    path = tmp_path / "export_branding.json"
    monkeypatch.setattr("core.system.export_branding_store.BRANDING_PATH", path)
    return path


def test_global_export_branding_persists(branding_path):
    save_global_export_branding(
        {
            "header_line1": "SEMINF - Secretaria Municipal de Infraestrutura",
            "header_line2": "DPO/SEMINF",
            "footer_line1": "Eng. Responsável",
            "show_brasao": False,
        }
    )
    assert branding_path.exists()
    loaded = get_global_export_branding()
    assert loaded.header_line1 == "SEMINF - Secretaria Municipal de Infraestrutura"
    assert loaded.header_line2 == "DPO/SEMINF"
    assert loaded.footer_line1 == "Eng. Responsável"
    assert loaded.show_brasao is False

    raw = json.loads(branding_path.read_text(encoding="utf-8"))
    assert raw["header_line1"] == "SEMINF - Secretaria Municipal de Infraestrutura"
