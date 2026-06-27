"""Testes de preços regionais em composições abertas."""

import pytest

from pricing.budget.price_bank_regional import apply_uf_to_open_composition


def test_apply_uf_uses_nested_regional_prices_not_top_level_keys():
    closed = [
        {
            "code": "95995",
            "description": "PAVIMENTO ASFÁLTICO",
            "unit": "M3",
            "price": 1528.59,
            "price_sem_desoneracao": 1532.31,
            "regional": {
                "SP": {"comd": 1528.59, "semd": 1532.31},
                "AM": {"comd": 2245.79, "semd": 2249.01},
            },
        }
    ]
    insumos = [
        {
            "code": "88316",
            "description": "ROLO COMPACTADOR",
            "unit": "CHP",
            "price": 100.0,
            "regional": {
                "SP": {"comd": 100.0, "semd": 101.0},
                "AM": {"comd": 150.0, "semd": 151.0},
            },
        }
    ]
    raw = {
        "code": "95995",
        "items": [
            {
                "code": "88316",
                "item_type": "equipamento",
                "coefficient": 0.5,
            }
        ],
    }

    am = apply_uf_to_open_composition(raw, uf="AM", closed_rows=closed, insumo_rows=insumos)
    assert am["total_price"] == 2245.79
    assert am["total_price_sem"] == 2249.01
    assert am["price_uf"] == "AM"
    assert am["items"][0]["unit_price"] == 150.0
    assert am["items"][0]["partial_cost"] == 75.0
    assert am["analytical_total_com"] == 75.0

    sp = apply_uf_to_open_composition(raw, uf="SP", closed_rows=closed, insumo_rows=insumos)
    assert sp["total_price"] == 1528.59
    assert sp["items"][0]["unit_price"] == 100.0


def test_apply_uf_falls_back_to_sp_when_uf_price_missing():
    """Insumo sem coleta na UF (tp2/%AS) usa preço SP — ex. CBUQ 1518 em AM."""
    insumos = [
        {
            "code": "1518",
            "description": "CBUQ",
            "unit": "T",
            "price": 512.5,
            "regional": {
                "SP": {"comd": 512.5, "semd": 512.5},
                "AM": {"comd": 0.0, "semd": 0.0},
            },
        }
    ]
    raw = {
        "code": "95995",
        "items": [
            {
                "code": "1518",
                "item_type": "insumo",
                "coefficient": 2.5663714,
                "unit_price": 0.0,
                "partial_cost": 0.0,
                "tp2": "AS",
            }
        ],
    }
    result = apply_uf_to_open_composition(
        raw, uf="AM", closed_rows=[], insumo_rows=insumos
    )
    assert result["items"][0]["unit_price"] == pytest.approx(512.5, abs=0.01)
    assert result["items"][0]["partial_cost"] == pytest.approx(1315.26, abs=0.5)


def test_apply_uf_keeps_stored_item_prices_when_insumo_missing():
    """SEMINF: CPUs com itens SINAPI sem catálogo de insumos na base regional."""
    closed = [
        {
            "code": "103519.3.9.SEMINF",
            "description": "DEMOLIÇÃO PARCIAL",
            "unit": "M3/SER.CG",
            "price": 15.91,
            "price_sem_desoneracao": 16.26,
            "regional": {"AM": {"comd": 15.91, "semd": 16.26}},
        }
    ]
    raw = {
        "code": "103519.3.9.SEMINF",
        "total_price": 15.91,
        "items": [
            {
                "code": "5678",
                "item_type": "equipamento",
                "coefficient": 0.0588,
                "unit_price": 176.66,
                "partial_cost": 10.38,
                "unit_price_sem": 180.0,
                "partial_cost_sem": 10.58,
                "tp2": "AS",
            },
        ],
    }

    result = apply_uf_to_open_composition(raw, uf="AM", closed_rows=closed, insumo_rows=[])
    assert result["total_price"] == 15.91
    assert result["items"][0]["unit_price"] == 176.66
    assert result["items"][0]["partial_cost"] == pytest.approx(10.38, abs=0.01)
    assert result["analytical_total_com"] == pytest.approx(10.38, abs=0.01)


def test_apply_uf_prefers_analytical_when_open_was_refreshed():
    """Fork SEMINF: total aberto recalculado diverge do sintético regional copiado."""
    closed = [
        {
            "code": "107634.3.9.SEMINF",
            "description": "USINAGEM DE CONCRETO ASFÁLTICO",
            "unit": "T",
            "price": 355.13,
            "price_sem_desoneracao": 355.35,
            "regional": {"AM": {"comd": 355.13, "semd": 355.35}},
        }
    ]
    raw = {
        "code": "107634.3.9.SEMINF",
        "total_price": 346.04,
        "total_price_sem": 346.26,
        "items": [
            {
                "code": "100642",
                "item_type": "equipamento",
                "coefficient": 0.009456,
                "unit_price": 311.29,
                "partial_cost": 2.94,
                "unit_price_sem": 312.0,
                "partial_cost_sem": 2.95,
            },
            {
                "code": "88309",
                "item_type": "insumo",
                "coefficient": 1.2,
                "unit_price": 285.0,
                "partial_cost": 342.0,
                "unit_price_sem": 286.0,
                "partial_cost_sem": 343.2,
            },
        ],
    }

    result = apply_uf_to_open_composition(raw, uf="AM", closed_rows=closed, insumo_rows=[])
    assert result["total_price"] == pytest.approx(344.94, abs=0.05)
    assert result["total_price_sem"] == pytest.approx(346.15, abs=0.05)
    assert result["analytical_total_com"] == pytest.approx(344.94, abs=0.05)
