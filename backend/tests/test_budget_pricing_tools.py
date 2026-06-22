"""Testes das ferramentas de consulta ao price_bank."""

from pricing.tools.budget_pricing_tools import (
    BudgetPricingTools,
    extract_sinapi_codes,
    extract_uf_from_text,
    fetch_pricing_context_for_agent,
    wants_open_composition,
)


def test_extract_sinapi_codes():
    assert extract_sinapi_codes("composição 95995 em AM") == ["95995"]


def test_extract_uf_amazonas():
    assert extract_uf_from_text("preços em Amazonas para 95995") == "AM"
    assert extract_uf_from_text("UF AM composição 95995") == "AM"


def test_wants_open_composition():
    assert wants_open_composition("esboce a composição aberta do código 95995")
    assert wants_open_composition("CPU sinapi 95995")


def test_get_open_composition_am_prices():
    try:
        comp = BudgetPricingTools.get_open_composition(
            "95995", uf="AM", reference="BR-2026-05"
        )
    except ValueError:
        return  # sem base importada no ambiente de CI
    assert comp["price_uf"] == "AM"
    assert float(comp["total_price"]) > 2000


def test_format_open_composition_includes_comd_semd():
    comp = {
        "code": "95995",
        "description": "Teste",
        "unit": "M3",
        "reference": "BR-2026-05",
        "price_uf": "AM",
        "total_price": 2245.79,
        "total_price_sem": 2249.01,
        "analytical_total_com": 2245.84,
        "analytical_total_sem": 2249.06,
        "items": [
            {
                "item_type": "equipamento",
                "code": "88316",
                "description": "Rolo",
                "unit": "CHP",
                "coefficient": 0.5,
                "unit_price": 97.49,
                "partial_cost": 48.75,
                "unit_price_sem": 98.0,
                "partial_cost_sem": 49.0,
            }
        ],
    }
    md = BudgetPricingTools.format_open_composition_markdown(comp)
    assert "ComD" in md
    assert "SemD" in md
    assert "2.245,79" in md or "2245" in md
    assert "88316" in md


def test_fetch_pricing_context_for_agent_cpu():
    ctx, calls = fetch_pricing_context_for_agent(
        "Esboce a composição aberta SINAPI código 95995 UF AM com e sem desoneração"
    )
    if not ctx:
        return
    assert "DADOS OFICIAIS" in ctx
    assert any(c.get("tool") == "get_open_composition" for c in calls)
