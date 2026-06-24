"""Testes — listagem e busca de CPUs abertas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.open_composition_catalog import list_open_compositions, search_open_compositions
from pricing.budget.price_bank_index import PriceBankIndex, PriceBankReferenceEntry
from pricing.budget.price_bank_store import CLOSED_NAME, OPEN_NAME, PriceBankStore


def _seed_open_bank(tmp_path, monkeypatch) -> str:
    from pricing.budget import price_bank_index as pbi

    monkeypatch.setattr(pbi, "PRICE_BANK_ROOT", tmp_path / "price_bank")
    pbi.PRICE_BANK_ROOT.mkdir(parents=True, exist_ok=True)

    ref = "BR-TEST-2026-04"
    store = PriceBankStore.for_reference(ref)
    store.root.mkdir(parents=True, exist_ok=True)

    open_map = {
        "10001": {
            "code": "10001",
            "description": "PAVIMENTO ASFALTICO",
            "unit": "M3",
            "total_price": 100.0,
            "total_price_sem": 101.0,
            "items": [
                {
                    "item_type": "insumo",
                    "code": "88309",
                    "description": "Cimento",
                    "unit": "KG",
                    "coefficient": 1.0,
                    "unit_price": 10.0,
                    "partial_cost": 10.0,
                    "unit_price_sem": 10.5,
                    "partial_cost_sem": 10.5,
                }
            ],
        },
        "20002": {
            "code": "20002",
            "description": "ALVENARIA DE VEDACAO",
            "unit": "M2",
            "total_price": 50.0,
            "total_price_sem": 51.0,
            "items": [],
        },
    }
    (store.root / OPEN_NAME).write_text(json.dumps(open_map), encoding="utf-8")
    closed = [
        {
            "code": "10001",
            "description": "PAVIMENTO ASFALTICO",
            "unit": "M3",
            "price": 100.0,
            "price_sem_desoneracao": 101.0,
            "regional": {"SP": {"comd": 100.0, "semd": 101.0}},
        },
        {
            "code": "20002",
            "description": "ALVENARIA DE VEDACAO",
            "unit": "M2",
            "price": 50.0,
            "price_sem_desoneracao": 51.0,
            "regional": {"SP": {"comd": 50.0, "semd": 51.0}},
        },
    ]
    (store.root / CLOSED_NAME).write_text(json.dumps(closed), encoding="utf-8")
    store.manifest_path.write_text(
        json.dumps(
            {
                "source": "sinapi",
                "reference": ref,
                "uf": "SP",
                "desonerado": False,
                "synced_at": "test",
                "counts": {"compositions_closed": 2, "compositions_open": 2, "insumos": 0},
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    idx = PriceBankIndex.load()
    idx.references = [PriceBankReferenceEntry(reference=ref, source="sinapi", default_uf="SP")]
    idx.save()
    return ref


def test_list_open_compositions_paginated(tmp_path, monkeypatch):
    ref = _seed_open_bank(tmp_path, monkeypatch)
    page = list_open_compositions(ref, uf="SP", offset=0, limit=1)
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert page["items"][0]["code"] in ("10001", "20002")


def test_search_open_compositions_by_description(tmp_path, monkeypatch):
    ref = _seed_open_bank(tmp_path, monkeypatch)
    hits = search_open_compositions("alvenaria", reference=ref, uf="SP")
    assert len(hits["items"]) == 1
    assert hits["items"][0]["code"] == "20002"


def test_search_open_compositions_by_code(tmp_path, monkeypatch):
    ref = _seed_open_bank(tmp_path, monkeypatch)
    hits = search_open_compositions("10001", reference=ref, uf="SP")
    assert hits["items"][0]["code"] == "10001"
    assert hits["items"][0]["match_kind"] == "code"
