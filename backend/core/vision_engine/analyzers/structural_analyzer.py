"""Structural Analyzer — projetos estruturais, fundações, armaduras."""

from __future__ import annotations

from typing import Any

from core.vision_engine.analyzers.base import AnalyzerType, BaseAnalyzer


class StructuralAnalyzer(BaseAnalyzer):
    analyzer_type = AnalyzerType.STRUCTURAL
    vision_mode = "estrutural"
    label = "Structural Analyzer"

    def enrich_context(self, ocr_data: dict[str, Any]) -> str:
        parts = [
            "[Structural Analyzer — projeto estrutural]",
            "Verificar: vigas, pilares, lajes, fundações, armaduras, cotas, seções, "
            "detalhamentos, NBR 6118/6120.",
        ]
        if ocr_data.get("texto"):
            parts.append(f"Texto OCR: {ocr_data['texto'][:2000]}")
        if ocr_data.get("tabelas"):
            parts.append(f"Tabelas/quantitativos: {len(ocr_data['tabelas'])}")
        return "\n".join(parts)
