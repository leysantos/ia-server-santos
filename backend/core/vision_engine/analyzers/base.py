"""Base dos analisadores especializados do Vision Engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Any


class AnalyzerType(StrEnum):
    PDF = "pdf"
    IMAGE = "image"
    PLANT = "plant"
    PCI = "pci"
    STRUCTURAL = "structural"


def route_analyzer(path: Path | str, *, mode: str | None = None) -> AnalyzerType:
    """Seleciona analisador conforme extensão, modo e nome do arquivo."""
    path = Path(path)
    ext = path.suffix.lower()
    name = path.name.lower()
    mode_key = (mode or "").strip().lower()

    if mode_key in ("pci", "planta_pci"):
        return AnalyzerType.PCI
    if mode_key in ("estrutural", "estrutura", "structural"):
        return AnalyzerType.STRUCTURAL
    if mode_key in ("planta", "arquitetura", "plant"):
        return AnalyzerType.PLANT
    if mode_key in ("quantitativo", "memorial"):
        return AnalyzerType.PDF

    if ext == ".pdf":
        if any(k in name for k in ("pci", "incendio", "incêndio", "sprinkler", "hidrante")):
            return AnalyzerType.PCI
        if any(k in name for k in ("est", "estrut", "fundacao", "fundação", "viga", "pilar")):
            return AnalyzerType.STRUCTURAL
        if any(k in name for k in ("arq", "planta", "layout", "arquitet")):
            return AnalyzerType.PLANT
        if any(k in name for k in ("memorial", "quantitativo", "planilha")):
            return AnalyzerType.PDF
        return AnalyzerType.PLANT

    if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}:
        return AnalyzerType.IMAGE

    return AnalyzerType.PDF


class BaseAnalyzer(ABC):
    analyzer_type: AnalyzerType
    vision_mode: str
    label: str

    @abstractmethod
    def enrich_context(self, ocr_data: dict[str, Any]) -> str:
        """Contexto textual adicional para o prompt de visão."""

    def build_payload(
        self,
        *,
        ocr_data: dict[str, Any],
        vision_result: dict[str, Any],
        technical_report: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "analyzer": self.analyzer_type.value,
            "analyzer_label": self.label,
            "vision_mode": self.vision_mode,
            "ocr": ocr_data,
            "vision_analysis": vision_result,
            "technical_report": technical_report,
        }
