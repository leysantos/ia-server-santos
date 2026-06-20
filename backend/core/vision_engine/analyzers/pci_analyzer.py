"""PCI Analyzer — projetos de prevenção e combate a incêndio."""

from __future__ import annotations

from typing import Any

from core.vision_engine.analyzers.base import AnalyzerType, BaseAnalyzer


class PciAnalyzer(BaseAnalyzer):
    analyzer_type = AnalyzerType.PCI
    vision_mode = "pci"
    label = "PCI Analyzer"

    def enrich_context(self, ocr_data: dict[str, Any]) -> str:
        parts = [
            "[PCI Analyzer — prevenção e combate a incêndio]",
            "Verificar: rotas de fuga, sinalização, hidrantes, sprinklers, compartimentação, "
            "distâncias, CBMPA/ITs aplicáveis.",
        ]
        if ocr_data.get("texto"):
            parts.append(f"Texto OCR: {ocr_data['texto'][:2000]}")
        return "\n".join(parts)
