"""Testes de preços regionais em composições abertas."""

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
