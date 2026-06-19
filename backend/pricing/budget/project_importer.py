from __future__ import annotations

from pathlib import Path
from typing import Any

from core.project_rag.project_file_extractors import extract_project_file_segments


class ProjectImporter:
    """Extrai texto de projeto (PDF, DOCX, Excel…) e gera orçamento via orchestrator."""

    MAX_CHARS = 12000

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def import_and_generate(
        self,
        path: Path,
        source_priority: list[str] | None = None,
        use_llm: bool = True,
        obra_type: str | None = None,
    ) -> dict[str, Any]:
        segments, fmt = extract_project_file_segments(path)
        text_parts = [s.text for s in segments]
        full_text = "\n\n".join(text_parts)
        if len(full_text) > self.MAX_CHARS:
            full_text = full_text[: self.MAX_CHARS] + "\n… [texto truncado]"

        prompt = (
            "Analise o documento de projeto abaixo e extraia informações para orçamento de obra civil.\n"
            "Identifique: escopo, dimensões, quantitativos, serviços e materiais mencionados.\n\n"
            f"--- Documento ({fmt}, {path.name}) ---\n{full_text}"
        )

        result = self._orchestrator.run(
            prompt,
            source_priority=source_priority,
            use_llm=use_llm,
            obra_type=obra_type,
        )
        result["project_import"] = {
            "filename": path.name,
            "format": fmt,
            "segments": len(segments),
            "chars_extracted": len(full_text),
        }
        return result
