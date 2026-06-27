"""Testes do store de esqueletos de orçamento."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pricing.budget import budget_skeleton_store as store


@pytest.fixture
def isolated_skeleton_store(tmp_path: Path, monkeypatch):
    path = tmp_path / "budget_skeletons.json"
    monkeypatch.setattr(store, "_STORE_PATH", path)
    yield path


def test_create_list_and_build_tree(isolated_skeleton_store):
    created = store.create_budget_skeleton(
        {
            "name": "Teste quadra",
            "obra_type": "RF",
            "etapas": [
                {
                    "name": "Preliminares",
                    "sub_etapas": [{"name": "Limpeza"}],
                }
            ],
        }
    )
    assert created["id"]
    items = store.list_budget_skeletons()
    assert any(i["id"] == created["id"] for i in items)

    sk = store.get_budget_skeleton(created["id"])
    assert sk is not None
    meta, roots = store.build_budget_tree_from_skeleton(sk)
    assert meta.projeto == "Teste quadra"
    assert len(roots) == 1
    assert roots[0].name == "PRELIMINARES"
    assert len(roots[0].children) == 1


def test_update_and_delete(isolated_skeleton_store):
    created = store.create_budget_skeleton({"name": "A", "etapas": [{"name": "E1", "sub_etapas": []}]})
    updated = store.update_budget_skeleton(created["id"], {"name": "B"})
    assert updated["name"] == "B"
    store.delete_budget_skeleton(created["id"])
    assert store.get_budget_skeleton(created["id"]) is None


def test_default_seed_on_first_read(isolated_skeleton_store):
    items = store.list_budget_skeletons()
    assert len(items) >= 1
    assert isolated_skeleton_store.is_file()
    data = json.loads(isolated_skeleton_store.read_text(encoding="utf-8"))
    assert data.get("version") == 1
