"""Testes de exportação PDF da CPU consultada."""

from __future__ import annotations

from pricing.budget.cpu_pdf_export import export_open_composition_pdf


def _sample_comp() -> dict:
    return {
        "code": "95995",
        "description": "Serviço de teste",
        "unit": "m²",
        "total_price": 125.50,
        "total_price_sem": 130.00,
        "price_uf": "SP",
        "reference": "BR-2026-05",
        "items": [
            {
                "item_type": "insumo",
                "code": "1111",
                "description": "Material A",
                "unit": "kg",
                "coefficient": 2.5,
                "unit_price": 10.0,
                "partial_cost": 25.0,
                "unit_price_sem": 11.0,
                "partial_cost_sem": 27.5,
            },
            {
                "item_type": "mao_obra",
                "code": "40809",
                "description": "Pedreiro",
                "unit": "h",
                "coefficient": 1.0,
                "unit_price": 100.5,
                "partial_cost": 100.5,
            },
        ],
    }


def test_export_open_composition_pdf_comd():
    pdf = export_open_composition_pdf(_sample_comp(), mode="comd", reference_label="BR-2026-05 / SP")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500


def test_export_open_composition_pdf_semd():
    pdf = export_open_composition_pdf(_sample_comp(), mode="semd")
    assert pdf[:4] == b"%PDF"
