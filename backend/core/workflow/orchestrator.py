"""Coordenador Workflow — orquestra microagentes via eventos."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.database.models import Project, ProjectFile
from core.workflow.agents.specialists import (
    CompareAgent,
    DrawingDetectorAgent,
    DwgAgent,
    DxfAgent,
    FolderAgent,
    IfcAgent,
    LayoutOptimizerAgent,
    NotificationAgent,
    ProjectAgent,
    PublishAgent,
    RevisionAgent,
    ScaleAgent,
    SheetAgent,
    SignatureAgent,
    TemplateAgent,
    VersionAgent,
    persist_drawing,
    resolve_file_agent,
)
from core.workflow.classification.file_classifier import classify_project_file
from core.workflow.events.bus import WorkflowEventBus, get_event_bus
from core.workflow.events.types import WorkflowEventType
from core.workflow.processed_files import file_already_processed

logger = logging.getLogger(__name__)

_PROCESSABLE_EXT = {".dwg", ".dxf", ".ifc", ".pdf"}


class WorkflowAgent:
    """Agente coordenador — delega para subagentes especializados."""

    name = "workflow"

    def __init__(self, bus: WorkflowEventBus | None = None) -> None:
        self.bus = bus or get_event_bus()
        self.project_agent = ProjectAgent()
        self.folder_agent = FolderAgent()
        self.dwg_agent = DwgAgent()
        self.dxf_agent = DxfAgent()
        self.ifc_agent = IfcAgent()
        self.scale_agent = ScaleAgent()
        self.drawing_agent = DrawingDetectorAgent()
        self.template_agent = TemplateAgent()
        self.sheet_agent = SheetAgent()
        self.layout_agent = LayoutOptimizerAgent()
        self.revision_agent = RevisionAgent()
        self.compare_agent = CompareAgent()
        self.publish_agent = PublishAgent()
        self.signature_agent = SignatureAgent()
        self.notification_agent = NotificationAgent()
        self.version_agent = VersionAgent()

    def initialize_project(
        self,
        project_id: str,
        db: Session,
        *,
        empresa_id: str | None = None,
        actor: str | None = "system",
    ) -> dict[str, Any]:
        ctx: dict[str, Any] = {"project_id": project_id}
        if empresa_id:
            ctx["empresa_id"] = empresa_id

        folder_result = self.folder_agent.run(ctx, db)
        self.bus.publish(
            WorkflowEventType.PROJECT_CREATED,
            {"project_id": project_id, "folders": folder_result.get("folders", [])},
            project_id=project_id,
            company_id=empresa_id,
            actor=actor,
            db=db,
        )
        return {"initialized": True, "folders": folder_result}

    def process_file(
        self,
        project_id: str,
        file_row: dict[str, Any] | ProjectFile,
        db: Session,
        *,
        actor: str | None = "system",
        force: bool = False,
    ) -> dict[str, Any]:
        if isinstance(file_row, ProjectFile):
            file_id = str(file_row.id)
            filename = file_row.filename
            storage_path = file_row.storage_path
        else:
            file_id = str(file_row["id"])
            filename = str(file_row["filename"])
            storage_path = str(file_row["storage_path"])

        ext = Path(filename).suffix.lower()
        if ext not in _PROCESSABLE_EXT:
            return {
                "status": "skipped",
                "reason": "unsupported_format",
                "filename": filename,
                "file_id": file_id,
            }

        if not force and file_already_processed(db, project_id, file_id):
            return {
                "status": "skipped",
                "reason": "already_processed",
                "filename": filename,
                "file_id": file_id,
            }

        project = db.get(Project, uuid.UUID(project_id))
        if project and not project.workflow_initialized:
            self.initialize_project(project_id, db, actor=actor)

        agent_key = resolve_file_agent(filename) or ("pdf" if ext == ".pdf" else None)
        file_kind = classify_project_file(filename, agent_key=agent_key)

        ctx: dict[str, Any] = {
            "project_id": project_id,
            "file_id": file_id,
            "filename": filename,
            "storage_path": storage_path,
            "responsavel": project.responsavel if project else "",
            "codigo": project.codigo if project else "",
            "revisao": project.versao_atual if project else "REV00",
            **file_kind,
        }

        self.bus.publish(
            WorkflowEventType.FILE_UPLOADED,
            {
                "file_id": file_id,
                "filename": filename,
                "tipo_arquivo": file_kind["tipo_arquivo"],
                "subtipo": file_kind["subtipo"],
            },
            project_id=project_id,
            company_id=str(project.empresa_id) if project and project.empresa_id else None,
            actor=actor,
            db=db,
        )

        if file_kind["tipo_arquivo"] == "documento":
            return self._process_document(ctx, db, actor=actor)

        return self._process_prancha(ctx, db, agent_key=agent_key, actor=actor)

    def _process_document(
        self,
        ctx: dict[str, Any],
        db: Session,
        *,
        actor: str,
    ) -> dict[str, Any]:
        """Indexa memorial, parecer, memória de cálculo etc. — sem prancha/revisão/entrega."""
        drawing_result = {
            "status": "ok",
            "agent": "file_classifier",
            "classificacao": ctx["subtipo"],
            "disciplina": self.drawing_agent._infer_discipline(ctx["subtipo"], ctx["filename"].lower()),
            "confidence": ctx.get("confidence", 0.8),
        }

        drawing = persist_drawing(
            db,
            project_id=uuid.UUID(ctx["project_id"]),
            project_file_id=uuid.UUID(ctx["file_id"]),
            classificacao=ctx["subtipo"],
            escala="—",
            disciplina=drawing_result["disciplina"],
            metadata={
                "tipo_arquivo": "documento",
                "subtipo": ctx["subtipo"],
                "filename": ctx["filename"],
                "pipeline": "index",
            },
        )

        self.bus.publish(
            WorkflowEventType.DRAWING_DETECTED,
            {
                "drawing_id": str(drawing.id),
                "tipo_arquivo": "documento",
                "subtipo": ctx["subtipo"],
                "classificacao": ctx["subtipo"],
            },
            project_id=ctx["project_id"],
            actor=actor,
            db=db,
        )

        db.flush()
        return {
            "status": "indexed",
            "pipeline": "document",
            "file_id": ctx["file_id"],
            "filename": ctx["filename"],
            "tipo_arquivo": "documento",
            "subtipo": ctx["subtipo"],
            "drawing_id": str(drawing.id),
        }

    def _process_prancha(
        self,
        ctx: dict[str, Any],
        db: Session,
        *,
        agent_key: str | None,
        actor: str,
    ) -> dict[str, Any]:
        """Pipeline completo para pranchas CAD/BIM/PDF."""
        project_id = ctx["project_id"]
        file_id = ctx["file_id"]
        filename = ctx["filename"]

        analysis: dict[str, Any] = {"status": "skipped", "reason": "pdf_prancha"}
        event_type = None

        if agent_key == "dwg":
            analysis = self.dwg_agent.run(ctx, db)
            event_type = WorkflowEventType.DWG_ANALYZED
        elif agent_key == "dxf":
            analysis = self.dxf_agent.run(ctx, db)
            event_type = WorkflowEventType.DXF_ANALYZED
        elif agent_key == "ifc":
            analysis = self.ifc_agent.run(ctx, db)
            event_type = WorkflowEventType.IFC_ANALYZED

        if event_type:
            self.bus.publish(
                event_type,
                {"file_id": file_id, "metadata": analysis.get("metadata", {})},
                project_id=project_id,
                actor=actor,
                db=db,
            )

        ctx["metadata"] = analysis.get("metadata", {})
        scale_result = self.scale_agent.run(ctx, db)
        ctx["escala"] = scale_result.get("escala", "1:100")

        drawing_result = self.drawing_agent.run(ctx, db)
        ctx.update(drawing_result)

        drawing = persist_drawing(
            db,
            project_id=uuid.UUID(project_id),
            project_file_id=uuid.UUID(file_id),
            classificacao=drawing_result.get("classificacao", ctx.get("subtipo", "prancha_tecnica")),
            escala=ctx["escala"],
            disciplina=drawing_result.get("disciplina"),
            metadata={
                **ctx.get("metadata", {}),
                "tipo_arquivo": "prancha",
                "subtipo": ctx.get("subtipo"),
                "filename": filename,
                "pipeline": "full",
            },
        )
        self.bus.publish(
            WorkflowEventType.DRAWING_DETECTED,
            {
                "drawing_id": str(drawing.id),
                "tipo_arquivo": "prancha",
                "classificacao": drawing.classificacao,
                "escala": drawing.escala,
            },
            project_id=project_id,
            actor=actor,
            db=db,
        )

        layout_result = self.layout_agent.run({**ctx, "drawings": [drawing_result]}, db)
        ctx["occupancy"] = layout_result.get("occupancy")

        template_result = self.template_agent.run(ctx, db)
        ctx.update(template_result)

        sheet_result = self.sheet_agent.run(ctx, db)
        self.bus.publish(
            WorkflowEventType.SHEET_GENERATED,
            {"sheet_id": sheet_result.get("sheet_id"), "escala": ctx["escala"]},
            project_id=project_id,
            actor=actor,
            db=db,
        )

        revision_result = self.revision_agent.run(
            {**ctx, "arquivo_origem_id": file_id},
            db,
        )
        self.bus.publish(
            WorkflowEventType.REVISION_CREATED,
            {"codigo": revision_result.get("codigo")},
            project_id=project_id,
            actor=actor,
            db=db,
        )

        version_result = self.version_agent.run(
            {
                "project_id": project_id,
                "mensagem": f"Prancha {filename}",
                "snapshot": {"file_id": file_id, "sheet_id": sheet_result.get("sheet_id"), "tipo": "prancha"},
            },
            db,
        )
        ctx["commit_hash"] = version_result.get("commit_hash")
        ctx["revisao"] = revision_result.get("codigo", ctx.get("revisao"))

        publish_result = self.publish_agent.run(ctx, db)
        self.bus.publish(
            WorkflowEventType.PDF_PUBLISHED,
            publish_result.get("outputs", {}),
            project_id=project_id,
            actor=actor,
            db=db,
        )

        signature_result = self.signature_agent.run(
            {**ctx, "pdf_path": publish_result.get("outputs", {}).get("pdf", "")},
            db,
        )
        self.bus.publish(
            WorkflowEventType.SIGNATURE_COMPLETED,
            {"hash": signature_result.get("hash")},
            project_id=project_id,
            actor=actor,
            db=db,
        )

        self.bus.publish(
            WorkflowEventType.PACKAGE_EXPORTED,
            publish_result.get("outputs", {}),
            project_id=project_id,
            actor=actor,
            db=db,
        )
        self.bus.publish(
            WorkflowEventType.DELIVERY_COMPLETED,
            {"project_id": project_id, "file_id": file_id, "tipo_arquivo": "prancha"},
            project_id=project_id,
            actor=actor,
            db=db,
        )

        self.notification_agent.run(
            {"message": f"Prancha processada: {filename}"},
            db,
        )

        db.flush()
        return {
            "status": "ok",
            "pipeline": "prancha",
            "file_id": file_id,
            "filename": filename,
            "tipo_arquivo": "prancha",
            "subtipo": ctx.get("subtipo"),
            "analysis": analysis,
            "scale": scale_result,
            "drawing": drawing_result,
            "sheet": sheet_result,
            "revision": revision_result,
            "version": version_result,
            "publish": publish_result,
            "signature": signature_result,
        }

    def run_full_pipeline(
        self,
        project_id: str,
        db: Session,
        *,
        actor: str | None = "system",
        force: bool = False,
    ) -> dict[str, Any]:
        project = db.get(Project, uuid.UUID(project_id))
        if not project:
            return {"status": "error", "reason": "project_not_found"}

        if not project.workflow_initialized:
            self.initialize_project(
                project_id,
                db,
                empresa_id=str(project.empresa_id) if project.empresa_id else None,
                actor=actor,
            )

        files = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == uuid.UUID(project_id))
            .order_by(ProjectFile.created_at)
            .all()
        )

        results: list[dict] = []
        skipped: list[dict] = []
        counts = {"pranchas": 0, "documentos": 0, "skipped": 0}

        for pf in files:
            ext = Path(pf.filename).suffix.lower()
            if ext not in _PROCESSABLE_EXT:
                continue
            result = self.process_file(project_id, pf, db, actor=actor, force=force)
            if result.get("status") == "skipped":
                skipped.append(result)
                counts["skipped"] += 1
            elif result.get("tipo_arquivo") == "documento":
                results.append(result)
                counts["documentos"] += 1
            elif result.get("pipeline") == "prancha" or result.get("tipo_arquivo") == "prancha":
                results.append(result)
                counts["pranchas"] += 1
            else:
                results.append(result)

        return {
            "status": "ok",
            "processed": len(results),
            "skipped": len(skipped),
            "total_files": len(files),
            "pranchas": counts["pranchas"],
            "documentos": counts["documentos"],
            "results": results,
            "skipped_files": skipped,
        }


class WorkflowOrchestrator(WorkflowAgent):
    """Alias explícito para camada de aplicação."""


_orchestrator: WorkflowOrchestrator | None = None


def get_workflow_orchestrator() -> WorkflowOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator
