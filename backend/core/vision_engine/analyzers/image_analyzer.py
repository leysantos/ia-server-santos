"""Image Analyzer — fotos de obra, vistorias, laudos fotográficos."""

from __future__ import annotations

from typing import Any

from core.project_review.vision_prompts import VisionAnalysisMode
from core.vision_engine.analyzers.base import AnalyzerType, BaseAnalyzer


class ImageAnalyzer(BaseAnalyzer):
    analyzer_type = AnalyzerType.IMAGE
    vision_mode = VisionAnalysisMode.OBRA
    label = "Image Analyzer"

    def __init__(self, *, vision_mode: str | None = None) -> None:
        if vision_mode:
            self.vision_mode = vision_mode

    def enrich_context(self, ocr_data: dict[str, Any]) -> str:
        parts = ["[Image Analyzer — foto de obra/vistoria]"]
        if ocr_data.get("texto"):
            parts.append(f"Texto detectado na imagem: {ocr_data['texto'][:1200]}")
        return "\n".join(parts)
