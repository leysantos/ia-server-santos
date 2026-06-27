"""Testes da fórmula de preço SINAPI Caixa (Analítico com Custo)."""

from __future__ import annotations

import pytest

from pricing.budget.sinapi_caixa_pricing import (
    build_insumo_regional_as,
    resolve_composicao_unit_price_caixa,
    resolve_insumo_unit_price_caixa,
)


def test_insumo_tier1_uf_price():
    regional = {"AM": {"comd": 815.0, "semd": 815.0}, "SP": {"comd": 535.0, "semd": 535.0}}
    assert resolve_insumo_unit_price_caixa(regional, "AM", sem=False) == 815.0


def test_insumo_tier2_regional_as_then_tier3_sp():
    regional = {"AM": {"comd": 0.0, "semd": 0.0}, "SP": {"comd": 512.5, "semd": 512.5}}
    regional_as = build_insumo_regional_as(
        isd_reg={"AM": 0.0, "SP": 512.5},
        icd_reg={"AM": 0.0, "SP": 512.5},
    )
    assert regional_as["AM"]["semd"] == pytest.approx(512.5)
    assert resolve_insumo_unit_price_caixa(
        regional, "AM", sem=True, regional_as=regional_as
    ) == pytest.approx(512.5)


def test_insumo_zero_when_no_price_anywhere():
    regional = {"AM": {"comd": 0.0, "semd": 0.0}, "SP": {"comd": 0.0, "semd": 0.0}}
    assert resolve_insumo_unit_price_caixa(regional, "AM", sem=True) == 0.0


def test_composicao_no_sp_fallback():
    regional = {
        "AM": {"comd": 93.04, "semd": 94.96},
        "SP": {"comd": 94.6, "semd": 96.78},
    }
    assert resolve_composicao_unit_price_caixa(regional, "AM", sem=True) == pytest.approx(94.96)
    regional_am_zero = {
        "AM": {"comd": 0.0, "semd": 0.0},
        "SP": {"comd": 94.6, "semd": 96.78},
    }
    assert resolve_composicao_unit_price_caixa(regional_am_zero, "AM", sem=True) == 0.0


def test_composicao_95995_march_am_matches_sheet():
    """CPU 95995 / AM / 03/2026 — valores SemD da planilha Caixa."""
    from pathlib import Path

    import pricing.sync.sinapi_parser as sp
    from pricing.budget.price_bank_regional import apply_uf_to_open_composition

    path = (
        Path(__file__).resolve().parents[1]
        / "knowledge"
        / "sync"
        / "price_bases"
        / "sinapi"
        / "SINAPI_Referência_2026_03.xlsx"
    )
    if not path.is_file():
        pytest.skip("Planilha local ausente")
    bank = sp.parse_sinapi_full_workbook(path, uf="AM")
    applied = apply_uf_to_open_composition(
        bank["open"]["95995"].to_dict(),
        uf="AM",
        closed_rows=[c.to_dict() for c in bank["closed"]],
        insumo_rows=[i.to_dict() for i in bank["insumos"]],
    )
    by_code = {i["code"]: i for i in applied["items"]}
    assert by_code["96464"]["unit_price_sem"] == pytest.approx(94.96, abs=0.02)
    assert by_code["1518"]["unit_price_sem"] == pytest.approx(512.5, abs=0.02)
    assert applied["total_price_sem"] == pytest.approx(1469.59, abs=0.05)
