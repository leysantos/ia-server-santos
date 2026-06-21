"""Testes — classificação prancha vs documento (Escola Metamorfose)."""

from __future__ import annotations

from core.workflow.classification.file_classifier import classify_project_file

METAMORFOSE_FILES = [
    "PPCI_ESCOLA_METAMORFOSE_R02.pdf",
    "ARQ_ESCOLA_METAMORFOSE_R02.pdf",
    "ARQ_ESCOLA_METAMORFSE_R01.pdf",
    "ITEM-02-MD_PPCI_CENTRO_EDUCACIONAL.pdf",
    "ITEM-03-MEMÓRIA DE CÁLCULO DE POPULAÇÃO.pdf",
    "ITEM-04-TERMO DE RESPONSABILIDADE PARA PORTA DE CORRER.pdf",
    "OBS-02-CARTA RESPOSTA AO PARECER TÉCNICO.pdf",
    "MEMORIAL DESCRITIVO PPCI ESCOLA METAMORFOSE.pdf",
    "PARECER TECNICO CBMAM ESCOLA METAMORFOSE.pdf",
]

EXPECTED_PRANCHAS = {
    "PPCI_ESCOLA_METAMORFOSE_R02.pdf",
    "ARQ_ESCOLA_METAMORFOSE_R02.pdf",
    "ARQ_ESCOLA_METAMORFSE_R01.pdf",
}


def test_metamorfose_nine_files_three_pranchas_six_documentos():
    results = {name: classify_project_file(name) for name in METAMORFOSE_FILES}
    pranchas = [n for n, r in results.items() if r["tipo_arquivo"] == "prancha"]
    documentos = [n for n, r in results.items() if r["tipo_arquivo"] == "documento"]

    assert len(METAMORFOSE_FILES) == 9
    assert len(pranchas) == 3
    assert len(documentos) == 6
    assert set(pranchas) == EXPECTED_PRANCHAS

    for name in EXPECTED_PRANCHAS:
        assert results[name]["pipeline"] == "full"
        assert results[name]["is_prancha"] is True

    for name in documentos:
        assert results[name]["pipeline"] == "index"
        assert results[name]["is_documento"] is True


def test_document_subtypes():
    r = classify_project_file("ITEM-03-MEMÓRIA DE CÁLCULO DE POPULAÇÃO.pdf")
    assert r["tipo_arquivo"] == "documento"
    assert r["subtipo"] == "memoria_calculo"

    r = classify_project_file("OBS-02-CARTA RESPOSTA AO PARECER TÉCNICO.pdf")
    assert r["tipo_arquivo"] == "documento"
    assert r["subtipo"] in ("carta", "parecer", "documento_tecnico")
