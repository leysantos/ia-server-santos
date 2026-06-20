"""Testes — Vision Analysis Engine (Gemma3 + Qwen3)."""

from __future__ import annotations

from core.project_review.vision_analysis_service import (
    VisionAnalysisService,
    extract_analysis,
    extract_technical_report,
    is_visual_file,
    suggest_mode_for_file,
)
from core.project_review.vision_prompts import VisionAnalysisMode, prompt_for_mode, supported_modes
from core.project_review.vision_router import VisionRouter, _model_installed, _resolve_vision_model_tags
from core.vision_engine.analyzers.base import AnalyzerType, route_analyzer
from core.vision_engine.pipeline import get_analyzer_instance


def test_supported_modes_includes_pci_estrutural():
    modes = {m["value"] for m in supported_modes()}
    assert VisionAnalysisMode.PCI in modes
    assert VisionAnalysisMode.ESTRUTURAL in modes


def test_prompt_pci_and_estrutural():
    assert "PCI" in prompt_for_mode(VisionAnalysisMode.PCI) or "pci" in prompt_for_mode(VisionAnalysisMode.PCI).lower()
    assert "estrutural" in prompt_for_mode(VisionAnalysisMode.ESTRUTURAL).lower()


def test_extract_analysis_wrapper_and_legacy():
    inner = {"disciplina": "estrutura", "resumo_tecnico": "Viga aparente"}
    assert extract_analysis({"analysis": inner}) == inner
    assert extract_analysis(inner) == inner
    assert extract_analysis(None) == {}


def test_extract_technical_report():
    report = {"resumo_executivo": "OK", "conclusao": "Aprovado"}
    assert extract_technical_report({"technical_report": report}) == report


def test_is_visual_file():
    assert is_visual_file("foto.jpg")
    assert is_visual_file("planta.pdf")
    assert is_visual_file("memorial.docx") is False


def test_suggest_mode_pci_estrutural():
    assert suggest_mode_for_file("pci_planta.pdf") == VisionAnalysisMode.PCI
    assert suggest_mode_for_file("estrutural_fundacao.pdf") == VisionAnalysisMode.ESTRUTURAL


def test_route_analyzer():
    assert route_analyzer("planta_arq.pdf") == AnalyzerType.PLANT
    assert route_analyzer("pci_sprinkler.pdf") == AnalyzerType.PCI
    assert route_analyzer("est_fundacao.pdf") == AnalyzerType.STRUCTURAL
    assert route_analyzer("obra.jpg") == AnalyzerType.IMAGE
    assert route_analyzer("memorial.pdf") == AnalyzerType.PDF


def test_get_analyzer_instance():
    assert get_analyzer_instance("pci.pdf").analyzer_type == AnalyzerType.PCI
    assert get_analyzer_instance("foto.jpg").analyzer_type == AnalyzerType.IMAGE


def test_model_installed_gemma():
    names = {"gemma3:12b", "qwen3:14b"}
    assert _model_installed(names, "gemma3:12b")
    assert _model_installed(names, "gemma3")
    tags = _resolve_vision_model_tags(names)
    assert "gemma3:12b" in tags


def test_parse_vision_json_strips_markdown():
    raw = '```json\n{"disciplina": "pci", "resumo_tecnico": "ok"}\n```'
    parsed = VisionRouter._parse_vision_json(raw)
    assert parsed["disciplina"] == "pci"


def test_aggregate_report_summary_with_technical():
    analyses = [
        {
            "filename": "a.pdf",
            "analyzer": "plant",
            "analysis": {"nao_conformidades": ["Escala ausente"], "resumo_tecnico": "Planta OK"},
            "technical_report": {
                "resumo_executivo": "Revisão parcial",
                "recomendacoes": ["Completar carimbo"],
            },
        },
    ]
    summary = VisionAnalysisService.aggregate_report_summary(analyses)
    assert summary["analyzed"] == 1
    assert "Escala ausente" in summary["nao_conformidades"]
    assert "Completar carimbo" in summary["recomendacoes"]
