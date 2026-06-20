"""Verificação de ferramentas disponíveis no workspace (projetos)."""

from __future__ import annotations

import importlib.util
from typing import Any

import requests

from config.settings import OLLAMA_BASE_URL, OLLAMA_CONNECT_TIMEOUT
from core.project_review.constants import TECHNICAL_MODEL, VISION_MODEL_PRIMARY
from core.project_review.vision_router import VisionRouter
from core.project_rag.project_file_extractors import PROJECT_INDEXABLE_SUFFIXES, PROJECT_UPLOAD_ACCEPT
from core.vision_engine.analyzers.base import AnalyzerType


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _model_installed(names: set[str], candidate: str) -> bool:
    if candidate in names:
        return True
    base = candidate.split(":")[0]
    return any(n == candidate or n.startswith(f"{base}:") for n in names)


def check_workspace_tools() -> dict[str, Any]:
    """Checklist completo de ferramentas do Vision Analysis Engine no workspace."""
    router = VisionRouter()
    vision_status = router.check_availability()

    ollama_models: set[str] = set()
    ollama_ok = False
    try:
        resp = requests.get(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags",
            timeout=(OLLAMA_CONNECT_TIMEOUT, 10),
        )
        resp.raise_for_status()
        ollama_ok = True
        ollama_models = {m.get("name", "") for m in resp.json().get("models", [])}
    except Exception as exc:
        vision_status["ollama_error"] = str(exc)

    gemma_ok = _model_installed(ollama_models, VISION_MODEL_PRIMARY)
    qwen_ok = _model_installed(ollama_models, TECHNICAL_MODEL)

    analyzers = [
        {
            "id": AnalyzerType.PDF.value,
            "label": "PDF Analyzer",
            "available": _module_available("fitz") or _module_available("pypdf"),
            "supports": ["memorial escaneado", "quadros de quantitativos", "PDF misto"],
        },
        {
            "id": AnalyzerType.IMAGE.value,
            "label": "Image Analyzer",
            "available": gemma_ok,
            "supports": ["fotos de obra", "vistorias", "laudos fotográficos"],
        },
        {
            "id": AnalyzerType.PLANT.value,
            "label": "Plant Analyzer",
            "available": gemma_ok and (_module_available("fitz") or True),
            "supports": ["plantas arquitetônicas", "pranchas técnicas"],
        },
        {
            "id": AnalyzerType.PCI.value,
            "label": "PCI Analyzer",
            "available": gemma_ok and qwen_ok,
            "supports": ["projetos PCI", "rotas de fuga", "sprinklers"],
        },
        {
            "id": AnalyzerType.STRUCTURAL.value,
            "label": "Structural Analyzer",
            "available": gemma_ok and qwen_ok,
            "supports": ["projetos estruturais", "fundações", "armaduras"],
        },
    ]

    reports = [
        {"id": "review", "label": "Relatório de Revisão", "route": "/projects/{id}/review/{rid}/export/review"},
        {"id": "nc", "label": "Relatório de Não Conformidades", "route": "/projects/{id}/review/{rid}/export/nc"},
        {"id": "parecer", "label": "Parecer Técnico", "route": "/projects/{id}/review/{rid}/export/parecer"},
        {"id": "memorial", "label": "Memorial Descritivo", "route": "/projects/{id}/review/{rid}/export/memorial:{disc}"},
        {"id": "tdr", "label": "TDR", "route": "/projects/{id}/review/{rid}/export/tdr"},
        {"id": "correcoes", "label": "Relatório de Correções", "route": "/projects/{id}/vision/report (correcoes)"},
        {"id": "relatorio_fotografico", "label": "Relatório Fotográfico", "route": "/projects/{id}/vision/report"},
        {"id": "laudo", "label": "Laudo de Vistoria", "route": "/projects/{id}/vision/report"},
    ]

    deps = {
        "pymupdf": _module_available("fitz"),
        "pypdf": _module_available("pypdf"),
        "pdfplumber": _module_available("pdfplumber"),
        "pillow": _module_available("PIL"),
        "paddleocr": _module_available("paddleocr"),
        "docx": _module_available("docx"),
    }

    pipeline_ready = gemma_ok and qwen_ok and ollama_ok and (deps["pymupdf"] or deps["pypdf"])

    return {
        "ready": pipeline_ready,
        "ollama_reachable": ollama_ok,
        "vision_model": VISION_MODEL_PRIMARY,
        "vision_model_ready": gemma_ok,
        "technical_model": TECHNICAL_MODEL,
        "technical_model_ready": qwen_ok,
        "installed_models": sorted(ollama_models),
        "analyzers": analyzers,
        "reports": reports,
        "workspace_upload": {
            "accept": PROJECT_UPLOAD_ACCEPT,
            "indexable_suffixes": sorted(PROJECT_INDEXABLE_SUFFIXES),
        },
        "dependencies": deps,
        "pipeline": [
            "Arquivo (workspace upload)",
            "OCR (PyMuPDF/pdfplumber/PaddleOCR)",
            f"Gemma3 Vision ({VISION_MODEL_PRIMARY})",
            "JSON Estruturado",
            f"Qwen3 Relatório ({TECHNICAL_MODEL})",
            "Export DOCX",
        ],
        "vision_status": vision_status,
        "frontend_routes": [
            "/projects",
            "/projects/{id}",
            "/projects/{id}/vision",
            "/projects/{id}/review",
        ],
    }
