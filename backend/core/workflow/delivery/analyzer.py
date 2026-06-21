"""Análise de arquivos para propostas do wizard de entrega."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.database.models import Project, ProjectFile
from core.workflow.agents.specialists import (
    DrawingDetectorAgent,
    DwgAgent,
    DxfAgent,
    IfcAgent,
    ScaleAgent,
)
from core.workflow.classification.file_classifier import classify_project_file
from core.workflow.nomenclature.engine import (
    discipline_code,
    extract_folha_hint,
    propose_item_nomenclature,
)
from core.workflow.delivery.normative_context import (
    refine_sheet_proposal_with_llm,
    retrieve_drawing_normative_context,
)


class DeliveryPackageAnalyzer:
    """Analisa arquivos selecionados e propõe nomenclatura / pastas / metadados."""

    def __init__(self) -> None:
        self.dwg = DwgAgent()
        self.dxf = DxfAgent()
        self.ifc = IfcAgent()
        self.scale = ScaleAgent()
        self.drawing = DrawingDetectorAgent()

    def analyze_file(
        self,
        pf: ProjectFile,
        *,
        project: Project | None,
        revisao_emissao: str,
        formato_padrao: str,
        folha_counters: dict[str, int],
    ) -> dict[str, Any]:
        filename = pf.filename
        ext = Path(filename).suffix.lower()
        kind = classify_project_file(filename)
        tipo_arquivo = kind["tipo_arquivo"]
        subtipo = kind.get("subtipo")

        if tipo_arquivo in ("cad", "bim") or ext in (".dwg", ".dxf", ".ifc"):
            role = "prancha"
        elif kind.get("is_prancha"):
            role = "prancha"
        elif kind.get("is_documento"):
            role = "documento"
        else:
            role = "documento"

        ctx: dict[str, Any] = {
            "filename": filename,
            "storage_path": pf.storage_path,
            "disciplina": project.disciplina if project else None,
        }

        metadata: dict[str, Any] = {}
        if ext == ".dwg":
            analysis = self.dwg.run(ctx)
            metadata = analysis.get("metadata", {})
        elif ext == ".dxf":
            analysis = self.dxf.run(ctx)
            metadata = analysis.get("metadata", {})
        elif ext == ".ifc":
            analysis = self.ifc.run(ctx)
            metadata = analysis.get("metadata", {})
        else:
            analysis = {"status": "skipped"}

        ctx["metadata"] = metadata
        scale_result = self.scale.run(ctx)
        drawing_result = self.drawing.run(ctx)

        disciplina = drawing_result.get("disciplina") or kind.get("subtipo", "geral")
        if "arq" in filename.lower():
            disciplina = "arquitetura"
        elif "ppci" in filename.lower() or "pci" in filename.lower():
            disciplina = "incendio"
        elif "est" in filename.lower():
            disciplina = "estrutural"

        disc_key = discipline_code(disciplina)
        hint = extract_folha_hint(filename)
        if hint is not None:
            folha = hint
            folha_counters[disc_key] = max(folha_counters.get(disc_key, 0), folha)
        else:
            folha_counters[disc_key] = folha_counters.get(disc_key, 0) + 1
            folha = folha_counters[disc_key]

        classificacao = drawing_result.get("classificacao", subtipo or "desenho_tecnico")
        formato = formato_padrao
        if role == "documento":
            formato = "—"

        proposal = propose_item_nomenclature(
            filename=filename,
            role=role,
            disciplina=disciplina,
            classificacao=classificacao,
            subtipo=subtipo,
            folha=folha,
            revisao_emissao=revisao_emissao,
            titulo=Path(filename).stem,
        )

        normative = retrieve_drawing_normative_context(
            filename=filename,
            disciplina=disciplina,
            tipo_desenho=proposal.get("tipo_desenho", ""),
            role=role,
        )

        enriched = {
            "project_file_id": str(pf.id),
            "filename": filename,
            "selected": True,
            "role": role,
            "disciplina": disciplina,
            "formato": formato,
            "escala": scale_result.get("escala", "1:100"),
            "classificacao": classificacao,
            "subtipo": subtipo,
            "tipo_arquivo": tipo_arquivo,
            **proposal,
            "analysis": {
                "cad": analysis,
                "drawing": drawing_result,
                "scale": scale_result,
                "classifier": kind,
                "metadata": metadata,
                "normative_rag": normative,
            },
        }

        from config.settings import get_settings

        enriched["ai_model"] = get_settings().ollama_chat_model

        if role == "prancha" and normative.get("rag_available"):
            enriched = refine_sheet_proposal_with_llm(enriched, normative)
        enriched["analysis"]["ai_model"] = enriched.get("ai_model")
        enriched["analysis"]["llm_refined"] = enriched.get("llm_refined", False)
        if enriched.get("observacao_normativa"):
            enriched["analysis"]["observacao_normativa"] = enriched["observacao_normativa"]

        return enriched

    def analyze_files(
        self,
        db: Session,
        project_id: uuid.UUID,
        file_ids: list[uuid.UUID],
        *,
        revisao_emissao: str = "REV00",
        formato_padrao: str = "A1",
    ) -> list[dict[str, Any]]:
        project = db.get(Project, project_id)
        files = (
            db.query(ProjectFile)
            .filter(
                ProjectFile.project_id == project_id,
                ProjectFile.id.in_(file_ids),
            )
            .order_by(ProjectFile.created_at)
            .all()
        )
        folha_counters: dict[str, int] = {}
        items: list[dict[str, Any]] = []
        for pf in files:
            items.append(
                self.analyze_file(
                    pf,
                    project=project,
                    revisao_emissao=revisao_emissao,
                    formato_padrao=formato_padrao,
                    folha_counters=folha_counters,
                )
            )
        return items
