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
            "[PCI Analyzer — prevenção e combate a incêndio / CBMAM-AM]",
            "Verificar: rotas de fuga tracejadas (IT-11/NBR 9077), sinalização (NBR 10898), "
            "saídas/UP, extintores, portão de correr (NT-03), tipo ocupação E-5 se educacional.",
        ]
        if ocr_data.get("texto"):
            parts.append(f"Texto OCR: {ocr_data['texto'][:2000]}")
        return "\n".join(parts)
