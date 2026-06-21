"""VisionAnalysisService — delega ao Vision Engine (OCR → Gemma3 → Qwen3)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.project_review.vision_prompts import VisionAnalysisMode, supported_modes
from core.vision_engine.pipeline import VisionEnginePipeline

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"})
VISUAL_SUFFIXES = IMAGE_SUFFIXES | frozenset({".pdf"})


def extract_analysis(vision_payload: dict[str, Any] | None) -> dict[str, Any]:
    """Compatível com payload novo (wrapper) e legado (análise flat)."""
    if not vision_payload:
        return {}
    inner = vision_payload.get("analysis")
    if isinstance(inner, dict):
        return inner
    if vision_payload.get("disciplina") or vision_payload.get("resumo_tecnico"):
        return vision_payload
    return {}


def extract_technical_report(vision_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not vision_payload:
        return {}
    report = vision_payload.get("technical_report")
    return report if isinstance(report, dict) else {}


def is_visual_file(path: Path | str) -> bool:
    return Path(path).suffix.lower() in VISUAL_SUFFIXES


def suggest_mode_for_file(path: Path | str, *, requested: str | None = None) -> str:
    if requested and requested in {m.value for m in VisionAnalysisMode}:
        return requested
    ext = Path(path).suffix.lower()
    name = Path(path).name.lower()
    if ext in IMAGE_SUFFIXES:
        if any(k in name for k in ("laudo", "vistoria", "patologia")):
            return VisionAnalysisMode.LAUDO
        if any(k in name for k in ("relatorio", "relatório", "foto", "acompanhamento")):
            return VisionAnalysisMode.RELATORIO_FOTOGRAFICO
        return VisionAnalysisMode.OBRA
    if ext == ".pdf":
        if any(k in name for k in ("pci", "incendio", "incêndio")):
            return VisionAnalysisMode.PCI
        if any(k in name for k in ("est", "estrut", "fundacao", "fundação")):
            return VisionAnalysisMode.ESTRUTURAL
        return VisionAnalysisMode.PLANTA
    return VisionAnalysisMode.OBRA


class VisionAnalysisService:
    """Orquestra análise visual por arquivo e agregação para relatórios."""

    def __init__(self, pipeline: VisionEnginePipeline | None = None) -> None:
        self.pipeline = pipeline or VisionEnginePipeline()
        self.router = self.pipeline.router

    @staticmethod
    def list_modes() -> list[dict[str, str]]:
        return supported_modes()

    def check_availability(self) -> dict[str, Any]:
        return self.pipeline.check_availability()

    def analyze_file(
        self,
        path: Path | str,
        *,
        mode: str | None = None,
        extra_context: str = "",
        filename: str | None = None,
    ) -> dict[str, Any]:
        path = Path(path).resolve()
        display = filename or path.name
        analysis_mode = suggest_mode_for_file(path, requested=mode)
        return self.pipeline.run(
            path,
            mode=mode or analysis_mode,
            extra_context=extra_context,
            filename=display,
        )

    def analyze_batch(
        self,
        items: list[tuple[Path, str, str | None]],
        *,
        mode: str | None = None,
        extra_context: str = "",
        skip_technical: bool = False,
    ) -> list[dict[str, Any]]:
        return self.pipeline.run_batch(
            items,
            mode=mode,
            extra_context=extra_context,
            skip_technical=skip_technical,
        )

    @staticmethod
    def aggregate_report_summary(analyses: list[dict[str, Any]]) -> dict[str, Any]:
        ok = [a for a in analyses if a.get("analysis") and not a.get("error")]
        errors = [a for a in analyses if a.get("error")]
        skipped = [a for a in analyses if a.get("skipped")]

        all_nc: list[str] = []
        all_recs: list[str] = []
        all_normas: set[str] = set()
        legendas: list[dict[str, str]] = []
        analyzers_used: set[str] = set()

        for row in ok:
            analyzers_used.add(str(row.get("analyzer") or row.get("analyzer_label") or ""))
            data = row.get("analysis") or {}
            tech = row.get("technical_report") or {}

            for nc in (data.get("nao_conformidades") or []) + (tech.get("nao_conformidades") or []):
                if isinstance(nc, str):
                    all_nc.append(nc)
                elif isinstance(nc, dict) and nc.get("descricao"):
                    all_nc.append(str(nc["descricao"]))

            for rec in (
                (data.get("recomendacoes") or [])
                + (tech.get("recomendacoes") or [])
                + (data.get("observacoes_fiscal") or [])
            ):
                if rec:
                    all_recs.append(str(rec))

            for norm in (data.get("normas_aplicaveis") or []) + (tech.get("normas_aplicaveis") or []):
                all_normas.add(str(norm))

            legenda = (
                data.get("legenda_relatorio")
                or data.get("legenda_laudo")
                or data.get("legenda_sugerida")
                or tech.get("resumo_executivo")
                or data.get("resumo_tecnico")
                or ""
            )
            if legenda:
                legendas.append({"filename": row.get("filename", ""), "legenda": str(legenda)[:500]})

        return {
            "total": len(analyses),
            "analyzed": len(ok),
            "errors": len(errors),
            "skipped": len(skipped),
            "analyzers_used": sorted(a for a in analyzers_used if a),
            "nao_conformidades": all_nc[:50],
            "recomendacoes": list(dict.fromkeys(all_recs))[:30],
            "normas_aplicaveis": sorted(all_normas),
            "legendas": legendas,
        }
