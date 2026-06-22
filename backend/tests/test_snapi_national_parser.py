"""Testes do parser SINAPI formato nacional 2025+."""

from __future__ import annotations

from pathlib import Path

import pytest

import pricing.sync.sinapi_parser as sp

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "bases-de-precos"
    / "sinapi-2026"
    / "SINAPI_Referência_2026_05.xlsx"
)


@pytest.mark.skipif(not FIXTURE.is_file(), reason="Planilha local nao presente")
def test_parse_national_workbook_sp():
    parse_fn = getattr(sp, "parse_sinapi_full_workbook")
    bank = parse_fn(FIXTURE, uf="SP")
    assert bank["format"] == "national"
    assert len(bank["closed"]) >= 10_000
    assert len(bank["open"]) >= 10_000
    assert len(bank["insumos"]) >= 4_000

    sample = bank["closed"][0]
    assert sample.code
    assert sample.price > 0
    assert sample.price_sem_desoneracao > 0

    comp = bank["open"].get("104658")
    assert comp is not None
    assert len(comp.items) >= 1
    assert comp.items[0].unit_price >= 0


@pytest.mark.skipif(not FIXTURE.is_file(), reason="Planilha local nao presente")
def test_composition_95995_sp_ccd_csd_matches_sheet():
    """Totais sintéticos SP devem bater com abas CCD (ComD) e CSD (SemD)."""
    parse_fn = getattr(sp, "parse_sinapi_full_workbook")
    bank_sp = parse_fn(FIXTURE, uf="SP")
    bank_am = parse_fn(FIXTURE, uf="AM")

    closed_sp = next(c for c in bank_sp["closed"] if c.code == "95995")
    open_sp = bank_sp["open"]["95995"]

    assert closed_sp.price == pytest.approx(1528.59, abs=0.02)
    assert closed_sp.price_sem_desoneracao == pytest.approx(1532.31, abs=0.02)
    assert open_sp.total_price == pytest.approx(1528.59, abs=0.02)
    assert open_sp.total_price_sem == pytest.approx(1532.31, abs=0.02)

    closed_am = next(c for c in bank_am["closed"] if c.code == "95995")
    assert closed_am.price == pytest.approx(2245.79, abs=0.02)
    assert closed_am.price != closed_sp.price
