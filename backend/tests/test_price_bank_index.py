"""Testes do índice multi-período do price_bank."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pricing.budget.price_bank_index import PRICE_BANK_ROOT, PriceBankIndex
from pricing.budget.price_bank_store import CompositionClosed, PriceBankStore


@pytest.fixture
def isolated_price_bank(monkeypatch, tmp_path: Path):
    root = tmp_path / "price_bank"
    root.mkdir()
    monkeypatch.setattr("pricing.budget.price_bank_index.PRICE_BANK_ROOT", root)
    return root


def _minimal_closed(code: str = "1") -> list[CompositionClosed]:
    return [
        CompositionClosed(
            code=code,
            description="Serviço teste",
            unit="un",
            price=10.0,
            price_sem_desoneracao=10.5,
        )
    ]


def test_save_bank_keeps_multiple_periods(isolated_price_bank: Path):
    store_may = PriceBankStore.for_reference("BR-2026-05")
    store_may.save_bank(
        source="sinapi",
        reference="BR-2026-05",
        closed=_minimal_closed("100"),
        open_compositions={},
        insumos=[],
        set_active=False,
    )

    store_apr = PriceBankStore.for_reference("BR-2026-04")
    store_apr.save_bank(
        source="sinapi",
        reference="BR-2026-04",
        closed=_minimal_closed("200"),
        open_compositions={},
        insumos=[],
        set_active=False,
    )

    idx = PriceBankIndex.load()
    refs = {r.reference for r in idx.references}
    assert refs == {"BR-2026-05", "BR-2026-04"}
    assert (isolated_price_bank / "BR-2026-05" / "manifest.json").is_file()
    assert (isolated_price_bank / "BR-2026-04" / "manifest.json").is_file()


def test_reconcile_with_disk_restores_sicro_and_seminf(isolated_price_bank: Path):
    for ref, source in (
        ("BR-SICRO-AM-2026-01", "cicro"),
        ("BR-DP-SEMINF-2026-04", "dp_seminf"),
    ):
        ref_dir = isolated_price_bank / ref
        ref_dir.mkdir()
        manifest = {
            "source": source,
            "reference": ref,
            "uf": "AM" if "AM" in ref else "SP",
            "synced_at": "2026-01-01T00:00:00+00:00",
            "counts": {"compositions_closed": 10},
            "metadata": {"year": 2026, "month": 1},
        }
        (ref_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (ref_dir / "compositions_closed.json").write_text("[]", encoding="utf-8")

    isolated_price_bank.joinpath("index.json").write_text(
        json.dumps({"active_reference": "", "references": []}),
        encoding="utf-8",
    )

    idx = PriceBankIndex.load()
    refs = {r.reference for r in idx.references}
    assert "BR-SICRO-AM-2026-01" in refs
    assert "BR-DP-SEMINF-2026-04" in refs


def test_reconcile_with_disk_removes_orphan_index_entry(isolated_price_bank: Path):
    isolated_price_bank.joinpath("index.json").write_text(
        json.dumps(
            {
                "active_reference": "BR-SICRO-SP-2026-04",
                "references": [
                    {
                        "reference": "BR-SICRO-SP-2026-04",
                        "source": "cicro",
                        "synced_at": "x",
                        "default_uf": "SP",
                        "counts": {"compositions_closed": 1},
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    idx = PriceBankIndex.load()
    assert any(r.reference == "BR-SICRO-SP-2026-04" for r in idx.references)

    idx.prune_orphan_references()
    reloaded = PriceBankIndex.load()
    assert not any(r.reference == "BR-SICRO-SP-2026-04" for r in reloaded.references)


def test_reconcile_with_disk_restores_missing_index_entry(isolated_price_bank: Path):
    ref_dir = isolated_price_bank / "BR-2026-03"
    ref_dir.mkdir()
    manifest = {
        "source": "sinapi",
        "reference": "BR-2026-03",
        "uf": "SP",
        "synced_at": "2026-01-01T00:00:00+00:00",
        "counts": {"compositions_closed": 99},
        "metadata": {"month": 3, "year": 2026},
    }
    (ref_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (ref_dir / "compositions_closed.json").write_text("[]", encoding="utf-8")

    isolated_price_bank.joinpath("index.json").write_text(
        json.dumps({"active_reference": "", "references": []}),
        encoding="utf-8",
    )

    idx = PriceBankIndex.load()
    assert any(r.reference == "BR-2026-03" for r in idx.references)
    assert idx.references[0].counts.get("compositions_closed") == 99


def test_register_updates_same_period_without_dropping_others(isolated_price_bank: Path):
    idx = PriceBankIndex.load()
    idx.register(
        "BR-2026-05",
        source="sinapi",
        default_uf="SP",
        synced_at="t1",
        counts={"compositions_closed": 1},
        set_active=False,
    )
    idx.register(
        "BR-2026-04",
        source="sinapi",
        default_uf="SP",
        synced_at="t2",
        counts={"compositions_closed": 2},
        set_active=False,
    )
    idx.register(
        "BR-2026-05",
        source="sinapi",
        default_uf="SP",
        synced_at="t3",
        counts={"compositions_closed": 100},
        set_active=False,
    )

    reloaded = PriceBankIndex.load()
    refs = {r.reference: r.counts["compositions_closed"] for r in reloaded.references}
    assert refs["BR-2026-05"] == 100
    assert refs["BR-2026-04"] == 2
