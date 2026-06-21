"""Testes — checklist PCI CBMAM e prompt reforçado."""

from __future__ import annotations

from core.project_review.vision_prompts import prompt_for_mode, VisionAnalysisMode
from core.vision_engine.pci_cbmam_checklist import run_pci_cbmam_checklist


def test_pci_prompt_requires_e5_and_tracejadas():
    prompt = prompt_for_mode(VisionAnalysisMode.PCI)
    assert "E-5" in prompt
    assert "tracejada" in prompt.lower() or "tracejadas" in prompt.lower()
    assert "IT-11" in prompt
    assert "NT-03" in prompt


def test_pci_checklist_metamorfose_sample():
    analyses = [
        {
            "filename": "PPCI_ESCOLA_METAMORFOSE_R02.pdf",
            "analysis_mode": "pci",
            "analysis": {
                "tipo_edificacao": "",
                "rotas_fuga": [],
                "saidas_emergencia": [{"tipo": "portão metalon"}],
                "sinalizacao": ["iluminação de emergência"],
            },
            "ocr": {"texto": "portão metalon saída"},
        },
        {
            "filename": "ITEM-03-MEMÓRIA DE CÁLCULO DE POPULAÇÃO.pdf",
            "analysis_mode": "pci",
            "analysis": {"resumo_tecnico": "94 pessoas, 2 UP"},
            "ocr": {"texto": "população 94 pessoas 2 unidades de passagem"},
        },
        {
            "filename": "ITEM-04-TERMO DE RESPONSABILIDADE PARA PORTA DE CORRER.pdf",
            "analysis_mode": "pci",
            "analysis": {},
            "ocr": {"texto": "termo NT-03 portão correr"},
        },
        {
            "filename": "OBS-02-CARTA RESPOSTA AO PARECER TÉCNICO.pdf",
            "analysis_mode": "pci",
            "analysis": {"tipo_edificacao": "Escola (E-5)"},
            "ocr": {"texto": "corrimão rampa largura corredor hall salas 4 e 5"},
        },
        {
            "filename": "ITEM-02-MD_PPCI_CENTRO_EDUCACIONAL.pdf",
            "analysis_mode": "pci",
            "analysis": {},
            "ocr": {"texto": "memorial descritivo assinado RT credenciamento"},
        },
    ]

    result = run_pci_cbmam_checklist(analyses)
    assert result["arquivos_analisados"] == 5
    assert result["total_itens"] >= 10

    by_id = {it["id"]: it for it in result["itens"]}
    assert by_id["it11_memoria_populacao"]["status"] == "conforme"
    assert by_id["nt03_termo_porta_correr"]["status"] == "conforme"
    assert by_id["it11_rotas_fuga_demarcadas"]["status"] in ("pendente", "parcial")
    assert result["pronto_cbmam"] is False
    assert result["rag_audit"]["rag_ativo_no_pipeline"] is False


def test_pci_checklist_rag_audit_when_sources_present():
    analyses = [
        {
            "filename": "PPCI_test.pdf",
            "analysis_mode": "pci",
            "analysis": {},
            "rag_sources": [{"norma": "IT-11", "trecho": "saídas"}],
            "normative_context": {"hits_count": 3, "rag_available": True},
        },
    ]
    result = run_pci_cbmam_checklist(analyses)
    assert result["rag_audit"]["analises_com_rag"] == 1
    assert result["rag_audit"]["rag_ativo_no_pipeline"] is True
