"""Pipeline completo: Arquivo → OCR → Gemma3 Vision → JSON → Qwen3 14B → Relatório."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.project_review.extraction.ocr_pipeline import extract_structured
from core.project_review.vision_prompts import VisionAnalysisMode
from core.project_review.vision_router import VisionRouter
from core.vision_engine.analyzers.base import AnalyzerType, route_analyzer
from core.vision_engine.analyzers.image_analyzer import ImageAnalyzer
from core.vision_engine.analyzers.pdf_analyzer import PdfAnalyzer
from core.vision_engine.analyzers.plant_analyzer import PlantAnalyzer
from core.vision_engine.analyzers.pci_analyzer import PciAnalyzer
from core.vision_engine.analyzers.structural_analyzer import StructuralAnalyzer
from core.vision_engine.technical_synthesis import synthesize_technical_report
from core.vision_engine.pci_knowledge import format_pci_knowledge_block, retrieve_pci_normative_context

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"})


def get_analyzer_instance(path: Path, mode: str | None = None):
    kind = route_analyzer(path, mode=mode)
    mode_key = (mode or "").strip().lower()

    if kind == AnalyzerType.PCI:
        return PciAnalyzer()
    if kind == AnalyzerType.STRUCTURAL:
        return StructuralAnalyzer()
    if kind == AnalyzerType.PLANT:
        return PlantAnalyzer()
    if kind == AnalyzerType.IMAGE:
        vision_mode = mode_key if mode_key in {m.value for m in VisionAnalysisMode} else VisionAnalysisMode.OBRA
        if mode_key in ("pci", "estrutural", "estrutura", "structural"):
            vision_mode = mode_key
        return ImageAnalyzer(vision_mode=vision_mode)
    return PdfAnalyzer()


class VisionEnginePipeline:
    """Orquestra OCR, visão Gemma3 e relatório técnico Qwen3."""

    def __init__(self, router: VisionRouter | None = None) -> None:
        self.router = router or VisionRouter()

    def check_availability(self) -> dict[str, Any]:
        return self.router.check_availability()

    def run(
        self,
        path: Path | str,
        *,
        mode: str | None = None,
        extra_context: str = "",
        filename: str | None = None,
        skip_technical: bool = False,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        path = Path(path).resolve()
        display = filename or path.name

        if not path.is_file():
            raise FileNotFoundError(str(path))

        analyzer = get_analyzer_instance(path, mode=mode)
        analysis_mode = analyzer.vision_mode

        if not self.router.should_use_vision(path):
            return {
                "filename": display,
                "analysis_mode": analysis_mode,
                "analyzer": analyzer.analyzer_type.value,
                "skipped": True,
                "reason": "formato_nao_visual",
                "analysis": None,
            }

        ocr_data: dict[str, Any] = {}
        ext = path.suffix.lower()
        if ext == ".pdf" or ext in _IMAGE_SUFFIXES:
            if on_progress:
                on_progress({"phase": "ocr", "message": f"OCR — {display}"})
            try:
                ocr_data = extract_structured(path)
            except Exception as exc:
                logger.debug("OCR falhou %s: %s", display, exc)
                ocr_data = {"format": ext.lstrip("."), "texto": "", "error": str(exc)}

        ocr_context = analyzer.enrich_context(ocr_data)
        combined_context = "\n".join(p for p in (ocr_context, extra_context) if p).strip()

        normative_context: dict[str, Any] | None = None
        if analysis_mode == VisionAnalysisMode.PCI:
            if on_progress:
                on_progress({"phase": "rag", "message": f"RAG CBMAM/NBR — {display}"})
            normative_context = retrieve_pci_normative_context(
                filename=display,
                ocr_text=str(ocr_data.get("texto") or ""),
                extra_context=extra_context,
            )
            knowledge_block = format_pci_knowledge_block(normative_context)
            combined_context = "\n\n".join(
                p for p in (combined_context, knowledge_block) if p
            ).strip()

        try:
            if on_progress:
                on_progress({"phase": "vision", "message": f"Gemma3 Vision — {display}"})
            vision_raw = self.router.analyze_file(
                path,
                mode=analysis_mode,
                extra_context=combined_context,
            )
            vision_model = vision_raw.pop("_model_used", None)

            technical_report: dict[str, Any] | None = None
            technical_model: str | None = None
            if not skip_technical:
                if on_progress:
                    on_progress({"phase": "technical", "message": f"Relatório Qwen3 — {display}"})
                tech_extra = extra_context
                if normative_context and normative_context.get("context_text"):
                    tech_extra = f"{extra_context}\n\n{normative_context['context_text']}".strip()
                technical_report = synthesize_technical_report(
                    filename=display,
                    analyzer=analyzer.label,
                    ocr_data=ocr_data,
                    vision_analysis=vision_raw,
                    extra_context=tech_extra,
                    analysis_mode=analysis_mode,
                )
                technical_model = technical_report.pop("_model_used", None)

            result: dict[str, Any] = {
                "filename": display,
                "analysis_mode": analysis_mode,
                "analyzer": analyzer.analyzer_type.value,
                "analyzer_label": analyzer.label,
                "skipped": False,
                "model_used": vision_model,
                "technical_model_used": technical_model,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "ocr": ocr_data,
                "analysis": vision_raw,
                "technical_report": technical_report,
            }
            if normative_context:
                result["normative_context"] = {
                    "rag_available": normative_context.get("rag_available"),
                    "hits_count": normative_context.get("hits_count"),
                    "bases_used": normative_context.get("bases_used"),
                }
                result["rag_sources"] = normative_context.get("sources") or []
            return result
        except Exception as exc:
            logger.warning("VisionEngine falhou %s: %s", display, exc)
            return {
                "filename": display,
                "analysis_mode": analysis_mode,
                "analyzer": analyzer.analyzer_type.value,
                "skipped": False,
                "error": str(exc),
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "ocr": ocr_data,
                "analysis": None,
                "technical_report": None,
            }

    def run_batch(
        self,
        items: list[tuple[Path, str, str | None]],
        *,
        mode: str | None = None,
        extra_context: str = "",
        skip_technical: bool = False,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for path, fname, file_id in items:
            row = self.run(
                path,
                mode=mode,
                extra_context=extra_context,
                filename=fname,
                skip_technical=skip_technical,
                on_progress=on_progress,
            )
            if file_id:
                row["project_file_id"] = file_id
            results.append(row)
        return results
