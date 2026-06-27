"""Testes do parser SINAPI formato nacional 2025+."""

from __future__ import annotations

from pathlib import Path

import pytest

import pricing.sync.sinapi_parser as sp

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "sync"
    / "price_bases"
    / "sinapi"
    / "SINAPI_Referência_2026_05.xlsx"
)
FIXTURE_ALT = (
    Path(__file__).resolve().parents[2]
    / "bases-de-precos"
    / "sinapi-2026"
    / "SINAPI_Referência_2026_05.xlsx"
)


def _fixture_path() -> Path | None:
    for candidate in (FIXTURE, FIXTURE_ALT):
        if candidate.is_file():
            return candidate
    return None


@pytest.mark.skipif(_fixture_path() is None, reason="Planilha local nao presente")
def test_parse_national_workbook_sp():
    parse_fn = getattr(sp, "parse_sinapi_full_workbook")
    bank = parse_fn(_fixture_path(), uf="SP")
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


@pytest.mark.skipif(_fixture_path() is None, reason="Planilha local nao presente")
def test_composition_95995_sp_ccd_csd_matches_sheet():
    """Totais sintéticos SP devem bater com abas CCD (ComD) e CSD (SemD)."""
    parse_fn = getattr(sp, "parse_sinapi_full_workbook")
    path = _fixture_path()
    bank_sp = parse_fn(path, uf="SP")
    bank_am = parse_fn(path, uf="AM")

    closed_sp = next(c for c in bank_sp["closed"] if c.code == "95995")
    open_sp = bank_sp["open"]["95995"]

    assert closed_sp.price == pytest.approx(1528.59, abs=0.02)
    assert closed_sp.price_sem_desoneracao == pytest.approx(1532.31, abs=0.02)
    assert open_sp.total_price == pytest.approx(1528.59, abs=0.02)
    assert open_sp.total_price_sem == pytest.approx(1532.31, abs=0.02)

    closed_am = next(c for c in bank_am["closed"] if c.code == "95995")
    assert closed_am.price == pytest.approx(2245.79, abs=0.02)
    assert closed_am.price != closed_sp.price


@pytest.mark.skipif(_fixture_path() is None, reason="Planilha local nao presente")
def test_sinapi_metadata_columns_imported():
    """Grupo, Classificação, Origem de Preço e %AS devem ser persistidos no banco."""
    from pricing.budget.price_bank_regional import apply_uf_to_open_composition

    bank = sp.parse_sinapi_full_workbook(_fixture_path(), uf="AM")

    alvenaria = next(
        c
        for c in bank["closed"]
        if c.grupo == "Alvenaria de Vedação"
        and "ALVENARIA DE VEDAÇÃO DE BLOCOS CERÂMICOS FURADOS NA HORIZONTAL DE 14X19X39"
        in c.description
    )
    assert alvenaria.grupo == "Alvenaria de Vedação"
    am_reg = alvenaria.regional["AM"]
    assert am_reg["semd"] == pytest.approx(78.58, abs=0.02)
    assert am_reg["pct_as_semd"] == pytest.approx(0.0055, abs=0.0001)

    insumo = next(i for i in bank["insumos"] if i.code == "11927")
    assert insumo.classificacao == "MATERIAL"
    assert insumo.origem_preco == "CR"

    comp = bank["open"]["95995"]
    assert comp.grupo
    item_with_origem = next(i for i in comp.items if i.origem_preco)
    assert item_with_origem.classificacao or item_with_origem.origem_preco

    raw = comp.to_dict()
    closed_rows = [c.to_dict() for c in bank["closed"]]
    insumo_rows = [i.to_dict() for i in bank["insumos"]]
    applied = apply_uf_to_open_composition(
        raw, uf="AM", closed_rows=closed_rows, insumo_rows=insumo_rows
    )
    closed_95995 = next(c for c in bank["closed"] if c.code == "95995")
    assert applied["grupo"] == comp.grupo
    assert applied["pct_as_comd"] == pytest.approx(
        closed_95995.regional["AM"]["pct_as_comd"], abs=0.0001
    )
    assert applied["tp2"] == "AS"
    assert any(i.get("tp2") == "AS" for i in applied["items"])


@pytest.mark.skipif(_fixture_path() is None, reason="Planilha local nao presente")
def test_composition_95995_cbuq_1518_am_uses_sp_when_no_local_coleta():
    """03/2026: insumo 1518 sem preço AM na ISD usa SP (512,50); 05/2026 usa AM (815)."""
    parse_fn = getattr(sp, "parse_sinapi_full_workbook")
    path = _fixture_path()
    bank_mar = parse_fn(
        Path(__file__).resolve().parents[1]
        / "knowledge"
        / "sync"
        / "price_bases"
        / "sinapi"
        / "SINAPI_Referência_2026_03.xlsx",
        uf="AM",
    )
    item_mar = next(i for i in bank_mar["open"]["95995"].items if i.code == "1518")
    assert item_mar.unit_price == pytest.approx(512.5, abs=0.02)

    bank_may = parse_fn(path, uf="AM")
    item_may = next(i for i in bank_may["open"]["95995"].items if i.code == "1518")
    assert item_may.unit_price == pytest.approx(815.0, abs=0.02)


@pytest.mark.skipif(_fixture_path() is None, reason="Planilha local nao presente")
def test_sinapi_labor_charges_am():
    bank = sp.parse_sinapi_full_workbook(_fixture_path(), uf="AM")
    labor = bank.get("labor_charges") or {}
    assert "AM" in labor
    am = labor["AM"]
    assert am["localidade"] == "MANAUS"
    assert am["horista_semd"] == pytest.approx(1.1416, abs=0.0001)
    assert am["mensalista_semd"] == pytest.approx(0.708, abs=0.0001)
    assert am["horista_comd"] == pytest.approx(0.9835, abs=0.0001)
