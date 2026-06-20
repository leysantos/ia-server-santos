"""Pipeline de ingestão de documentos (Módulo B)."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Any

from core.project_review.discipline_detector import detect_discipline
from core.project_review.extraction.bim_analyzer import analyze_ifc
from core.project_review.extraction.cad_analyzer import analyze_dxf
from core.project_review.extraction.ocr_pipeline import extract_structured
from core.project_review.vision_analysis_service import VisionAnalysisService
from core.project_review.vision_router import VisionRouter
from core.project_rag.project_file_extractors import extract_project_file_segments

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Processa arquivos do projeto: extração, visão, disciplina."""

    def __init__(self, *, enable_vision: bool = True):
        self.enable_vision = enable_vision
        self.vision = VisionAnalysisService()

    def process_file(self, path: Path, filename: str | None = None) -> dict[str, Any]:
        path = Path(path).resolve()
        name = filename or path.name
        ext = path.suffix.lower()

        if ext == ".zip":
            return self._process_zip(path, name)

        extraction = self._extract_by_format(path, ext)
        text_sample = extraction.get("texto") or self._segments_text(path)
        discipline = detect_discipline(
            name,
            text_sample=text_sample,
            format_key=extraction.get("format", ext.lstrip(".")),
        )
        extraction["disciplina_detectada"] = discipline

        vision_json: dict[str, Any] | None = None
        if self.enable_vision and self.vision.router.should_use_vision(path):
            mode = "planta" if ext == ".pdf" else "obra"
            result = self.vision.analyze_file(path, mode=mode, extra_context=text_sample[:1500], filename=name)
            vision_json = result
            analysis = result.get("analysis") or {}
            if analysis.get("disciplina") and analysis["disciplina"] != "desconhecida":
                discipline = analysis["disciplina"]

        return {
            "filename": name,
            "format_key": extraction.get("format", ext.lstrip(".")),
            "discipline": discipline,
            "extraction_json": extraction,
            "vision_json": vision_json,
        }

    def _extract_by_format(self, path: Path, ext: str) -> dict[str, Any]:
        if ext == ".ifc":
            return analyze_ifc(path)
        if ext == ".dxf":
            return analyze_dxf(path)
        if ext in {".pdf", ".png", ".jpg", ".jpeg"}:
            return extract_structured(path)
        if ext in {".docx", ".xlsx", ".xls", ".csv", ".txt", ".md", ".dwg"}:
            text = self._segments_text(path)
            return {"format": ext.lstrip("."), "texto": text, "tabelas": []}
        return {"format": ext.lstrip("."), "texto": "", "tabelas": []}

    def _segments_text(self, path: Path) -> str:
        try:
            segments, _ = extract_project_file_segments(path)
            return "\n".join(s.text for s in segments if s.text)[:80_000]
        except Exception as exc:
            logger.debug("segment extract %s: %s", path.name, exc)
            return ""

    def _process_zip(self, path: Path, name: str) -> dict[str, Any]:
        members: list[dict[str, Any]] = []
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                inner_name = Path(info.filename).name
                if not inner_name or inner_name.startswith("."):
                    continue
                suffix = Path(inner_name).suffix.lower()
                if suffix not in {".pdf", ".docx", ".xlsx", ".dxf", ".ifc", ".png", ".jpg", ".dwg"}:
                    continue
                dest = path.parent / f"_zip_{path.stem}_{inner_name}"
                dest.write_bytes(zf.read(info))
                try:
                    members.append(self.process_file(dest, inner_name))
                finally:
                    dest.unlink(missing_ok=True)

        combined_text = "\n".join(
            (m.get("extraction_json") or {}).get("texto", "") for m in members
        )
        return {
            "filename": name,
            "format_key": "zip",
            "discipline": detect_discipline(name, text_sample=combined_text),
            "extraction_json": {
                "format": "zip",
                "members": len(members),
                "texto": combined_text[:50_000],
                "arquivos": [m["filename"] for m in members],
            },
            "vision_json": None,
            "members": members,
        }
