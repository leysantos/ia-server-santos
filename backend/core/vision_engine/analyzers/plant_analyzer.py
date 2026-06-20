"""Plant Analyzer — plantas arquitetônicas e pranchas técnicas."""

from __future__ import annotations

from typing import Any

from core.project_review.vision_prompts import VisionAnalysisMode
from core.vision_engine.analyzers.base import AnalyzerType, BaseAnalyzer


class PlantAnalyzer(BaseAnalyzer):
    analyzer_type = AnalyzerType.PLANT
    vision_mode = VisionAnalysisMode.PLANTA
    label = "Plant Analyzer"

    def enrich_context(self, ocr_data: dict[str, Any]) -> str:
        parts = ["[Plant Analyzer — planta arquitetônica/prancha técnica]"]
        for key in ("escalas", "carimbos", "legendas", "cotas"):
            items = ocr_data.get(key) or []
            if items:
                parts.append(f"{key.title()}: {'; '.join(str(i) for i in items[:10])}")
        if ocr_data.get("texto"):
            parts.append(f"Texto extraído: {ocr_data['texto'][:2000]}")
        return "\n".join(parts)
