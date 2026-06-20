"""PDF Analyzer — memorial escaneado, quantitativos, documentos mistos."""

from __future__ import annotations

from typing import Any

from core.project_review.vision_prompts import VisionAnalysisMode
from core.vision_engine.analyzers.base import AnalyzerType, BaseAnalyzer


class PdfAnalyzer(BaseAnalyzer):
    analyzer_type = AnalyzerType.PDF
    vision_mode = VisionAnalysisMode.PLANTA
    label = "PDF Analyzer"

    def enrich_context(self, ocr_data: dict[str, Any]) -> str:
        parts = ["[PDF Analyzer — memorial/quantitativo/documento escaneado]"]
        if ocr_data.get("texto"):
            parts.append(f"Texto OCR ({len(ocr_data['texto'])} chars): {ocr_data['texto'][:2500]}")
        if ocr_data.get("tabelas"):
            parts.append(f"Tabelas detectadas: {len(ocr_data['tabelas'])}")
        if ocr_data.get("carimbos"):
            parts.append("Carimbos: " + "; ".join(str(c) for c in ocr_data["carimbos"][:8]))
        if ocr_data.get("quadros"):
            parts.append(f"Quadros: {len(ocr_data['quadros'])}")
        return "\n".join(parts)
