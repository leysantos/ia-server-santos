"""Testes OrçaFacil — índice da base do modelo."""

from __future__ import annotations

from pathlib import Path

import pytest

from pricing.budget.orca_facil.base_index import build_base_index_from_model


CONT_DREN = (
    Path(__file__).resolve().parents[2]
    / "CONT_DREN_COLONIA_ANTONIO_ALEIXO_R01"
    / "00_MOD_MC_OR_R00-Maio2026-10-07-2026v9.3.1.xlsm"
)


@pytest.mark.skipif(not CONT_DREN.is_file(), reason="modelo CONT_DREN ausente")
def test_build_base_index_from_cont_dren_model():
    idx = build_base_index_from_model(CONT_DREN)
    assert idx.size > 1000
    assert idx.sheet_name and "base" in idx.sheet_name.lower()

    gabiao = idx.get_by_code("92743")
    assert gabiao is not None
    assert "GABIÃO" in gabiao.description.upper() or "GABIAO" in gabiao.description.upper().replace("Ã", "A")
    assert gabiao.price_comd > 0

    hits = idx.search_base("muro de gabiao", top_k=5)
    assert hits
    codes = {h[0].code for h in hits}
    assert "92743" in codes or any("92743" in c for c in codes)


def test_search_empty_query():
    from pricing.budget.orca_facil.base_index import ModelPriceBaseIndex, BaseRow

    idx = ModelPriceBaseIndex(
        sheet_name="Base",
        rows=[
            BaseRow("1", "TAPUME METALICO", "M2", 10.0, 9.0),
            BaseRow("2", "ENGENHEIRO CIVIL", "MES", 100.0, 90.0),
        ],
    )
    assert idx.search_base("") == []
    assert idx.get_by_code("1") is not None
    assert idx.search_base("engenheiro")[0][0].code == "2"
