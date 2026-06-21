"""Testes — Wizard de Entrega Fase 3."""

from __future__ import annotations

from core.workflow.nomenclature.engine import (
    build_drawing_code,
    discipline_code,
    propose_item_nomenclature,
)


def test_build_drawing_code_arq_example():
    code = build_drawing_code(
        disciplina="arquitetura",
        folha=1,
        tipo="PLANTA",
        descricao="TERREO",
        revisao="R02",
    )
    assert code == "ARQ-FL01-PLANTA-TERREO-R02"


def test_build_drawing_code_est_example():
    code = build_drawing_code(
        disciplina="estrutural",
        folha=1,
        tipo="FORMA",
        descricao="FORMAS",
        revisao="R01",
    )
    assert code.startswith("EST-FL01-FORMA")
    assert code.endswith("R01")


def test_propose_prancha_vs_documento():
    prancha = propose_item_nomenclature(
        filename="ARQ_ESCOLA_METAMORFOSE_R02.pdf",
        role="prancha",
        disciplina="arquitetura",
        classificacao="planta_baixa",
        subtipo="prancha_arquitetura",
        folha=1,
        revisao_emissao="REV03",
    )
    assert prancha["pasta_destino"] == "01_PRANCHAS/ARQ"
    assert "ARQ-FL01" in prancha["codigo_sugerido"]

    doc = propose_item_nomenclature(
        filename="ITEM-03-MEMÓRIA DE CÁLCULO.pdf",
        role="documento",
        disciplina="incendio",
        classificacao="memoria_calculo",
        subtipo="memoria_calculo",
        folha=1,
        revisao_emissao="REV03",
    )
    assert doc["pasta_destino"] == "03_MEMORIAS_DE_CALCULO"


def test_discipline_code():
    assert discipline_code("arquitetura") == "ARQ"
    assert discipline_code("incendio") == "PCI"
