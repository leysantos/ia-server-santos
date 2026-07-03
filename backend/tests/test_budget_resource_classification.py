"""Testes de classificação insumo vs mão de obra."""

from __future__ import annotations

from pricing.budget.budget_resource_classification import (
    is_direct_labor_role,
    is_histogram_direct_labor,
    is_indirect_mo_charge,
    is_labor_descriptor,
    resolve_resource_category,
)


def test_mensalista_is_labor_by_description_and_unit():
    assert is_labor_descriptor("ENGENHEIRO CIVIL DE OBRA PLENO (MENSALISTA)", "MES")
    assert is_labor_descriptor("ALMOXARIFE (MENSALISTA)", "MES")
    assert not is_labor_descriptor("Cimento Portland CP II", "kg")


def test_resolve_mensalista_as_mao_obra_even_with_insumo_type():
    item = {
        "item_type": "insumo",
        "code": "40813",
        "description": "ENGENHEIRO CIVIL DE OBRA PLENO (MENSALISTA)",
        "unit": "MES",
        "classificacao": "",
    }
    assert resolve_resource_category(item) == "mao_obra"


def test_resolve_material_by_classificacao():
    item = {
        "item_type": "insumo",
        "code": "88316",
        "description": "Cimento Portland",
        "unit": "kg",
        "classificacao": "MATERIAL",
    }
    assert resolve_resource_category(item) == "insumo"


def test_resolve_mao_obra_by_classificacao_sinapi():
    item = {
        "item_type": "insumo",
        "code": "40809",
        "description": "ALMOXARIFE",
        "unit": "MES",
        "classificacao": "MAO DE OBRA",
    }
    assert resolve_resource_category(item) == "mao_obra"


def test_indirect_mo_charges():
    assert is_indirect_mo_charge("EPI - FAMILIA SERVENTE - MENSALISTA (ENCARGOS COMPLEMENTARES)")
    assert is_indirect_mo_charge("FERRAMENTAS - FAMILIA PEDREIRO - MENSALISTA")
    assert is_indirect_mo_charge("SEGURO - MENSALISTA (COLETADO CAIXA - ENCARGOS COMPLEMENTARES)")
    assert is_indirect_mo_charge("TRANSPORTE - MENSALISTA (COLETADO CAIXA - ENCARGOS COMPLEMENTARES)")
    assert is_indirect_mo_charge("LOCACAO DE CONTAINER 2,30 X 6,00 M - ESCRITORIO")
    assert not is_indirect_mo_charge("PEDREIRO COM ENCARGOS COMPLEMENTARES")
    assert not is_indirect_mo_charge("ENGENHEIRO CIVIL DE OBRA PLENO (MENSALISTA)")


def test_direct_labor_roles():
    assert is_direct_labor_role("PEDREIRO COM ENCARGOS COMPLEMENTARES")
    assert is_direct_labor_role("SERVENTE (MENSALISTA)")
    assert is_direct_labor_role("VIGIA DIURNO (MENSALISTA)")
    assert is_direct_labor_role("Pré-marcador")
    assert not is_direct_labor_role("SEGURO - MENSALISTA")


def test_histogram_direct_labor_filter():
    pedreiro = {
        "item_type": "insumo",
        "description": "PEDREIRO COM ENCARGOS COMPLEMENTARES",
        "unit": "H",
        "classificacao": "",
    }
    epi = {
        "item_type": "insumo",
        "description": "EPI - FAMILIA SERVENTE - MENSALISTA (ENCARGOS COMPLEMENTARES)",
        "unit": "MES",
        "classificacao": "",
    }
    transporte = {
        "item_type": "insumo",
        "description": "TRANSPORTE - MENSALISTA (COLETADO CAIXA - ENCARGOS COMPLEMENTARES)",
        "unit": "MES",
        "classificacao": "",
    }
    engenheiro = {
        "item_type": "insumo",
        "description": "ENGENHEIRO CIVIL DE OBRA PLENO (MENSALISTA)",
        "unit": "MES",
        "classificacao": "",
    }

    assert is_histogram_direct_labor(pedreiro)
    assert not is_histogram_direct_labor(epi)
    assert not is_histogram_direct_labor(transporte)
    assert is_histogram_direct_labor(engenheiro)

