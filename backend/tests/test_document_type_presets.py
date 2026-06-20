"""Testes — presets configuráveis de tipo de documento."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.knowledge import document_type_presets as mod


@pytest.fixture
def presets_file(tmp_path, monkeypatch):
    path = tmp_path / "document_type_presets.json"
    monkeypatch.setattr(mod, "PRESETS_PATH", path)
    return path


def test_list_presets_seeds_defaults(presets_file):
    presets = mod.list_presets()
    assert len(presets) >= 2
    assert any(p["id"] == "normas_pci_cbmam" for p in presets)
    assert presets_file.is_file()


def test_create_update_delete_preset(presets_file):
    mod.list_presets()
    created = mod.create_preset(
        {
            "label": "Manuais Hidráulicos",
            "content_type": "manuais",
            "discipline": "HIDROSSANITÁRIO",
        }
    )
    assert created["id"] == "manuais_hidraulicos"
    updated = mod.update_preset(created["id"], {"label": "Manuais Hidráulicos Rev. 2"})
    assert updated["label"] == "Manuais Hidráulicos Rev. 2"
    deleted = mod.delete_preset(created["id"])
    assert deleted["id"] == created["id"]
    assert mod.get_preset(created["id"]) is None


def test_invalid_discipline_raises(presets_file):
    mod.list_presets()
    with pytest.raises(mod.DocumentTypePresetError):
        mod.create_preset(
            {
                "label": "Tipo inválido",
                "content_type": "nbrs",
                "discipline": "DISCIPLINA_INEXISTENTE",
            }
        )
