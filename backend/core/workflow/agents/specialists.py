"""Agentes especializados do Workflow Projetos."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.database.models import Project, ProjectFile
from core.database.workflow_models import (
    ProjectFolder,
    WorkflowDrawing,
    WorkflowRevision,
    WorkflowSheet,
    WorkflowVersion,
)
from core.workflow.agents.base import BaseWorkflowAgent
from core.workflow.events.types import DEFAULT_FOLDER_STRUCTURE, SUPPORTED_SCALES
from core.workflow.template_engine.engine import build_sheet_context, render_default_sheet


class ProjectAgent(BaseWorkflowAgent):
    name = "project"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        if db is None:
            return {"status": "skipped", "reason": "no_db"}
        project_id = uuid.UUID(str(context["project_id"]))
        project = db.get(Project, project_id)
        if not project:
            return {"status": "error", "reason": "project_not_found"}

        updates: dict[str, Any] = {}
        for field in ("codigo", "cliente", "responsavel", "disciplina", "status"):
            if field in context and context[field] is not None:
                setattr(project, field, context[field])
                updates[field] = context[field]

        if context.get("empresa_id"):
            project.empresa_id = uuid.UUID(str(context["empresa_id"]))
            updates["empresa_id"] = str(project.empresa_id)

        db.flush()
        return {"status": "ok", "agent": self.name, "updates": updates}


class FolderAgent(BaseWorkflowAgent):
    name = "folder"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        if db is None:
            return {"status": "skipped", "reason": "no_db"}
        project_id = uuid.UUID(str(context["project_id"]))
        existing = (
            db.query(ProjectFolder)
            .filter(ProjectFolder.project_id == project_id)
            .count()
        )
        if existing > 0:
            return {"status": "ok", "agent": self.name, "created": 0, "existing": existing}

        created = []
        for idx, spec in enumerate(DEFAULT_FOLDER_STRUCTURE):
            folder = ProjectFolder(
                project_id=project_id,
                nome=str(spec["nome"]),
                path=str(spec["path"]),
                disciplina=spec.get("disciplina"),
                sort_order=idx,
            )
            db.add(folder)
            created.append(spec["path"])

        project = db.get(Project, project_id)
        if project:
            project.workflow_initialized = True

        db.flush()
        return {"status": "ok", "agent": self.name, "created": len(created), "folders": created}


class DwgAgent(BaseWorkflowAgent):
    name = "dwg"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        path = Path(str(context.get("storage_path", "")))
        if not path.exists():
            return {"status": "error", "reason": "file_not_found"}

        metadata: dict[str, Any] = {"format": "dwg", "layers": [], "blocks": [], "layouts": []}
        try:
            import ezdxf

            doc = ezdxf.readfile(str(path))
            msp = doc.modelspace()
            metadata["layers"] = sorted({layer.dxf.name for layer in doc.layers})
            metadata["blocks"] = sorted({b.name for b in doc.blocks if not b.name.startswith("*")})
            metadata["layouts"] = list(doc.layout_names())
            metadata["entity_count"] = len(list(msp))
        except Exception as exc:
            metadata["warning"] = f"ezdxf fallback: {exc}"
            metadata["layers"] = []
            metadata["note"] = "ODA/LibreDWG não configurado — metadados parciais"

        return {"status": "ok", "agent": self.name, "metadata": metadata}


class DxfAgent(DwgAgent):
    name = "dxf"


class IfcAgent(BaseWorkflowAgent):
    name = "ifc"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        path = Path(str(context.get("storage_path", "")))
        if not path.exists():
            return {"status": "error", "reason": "file_not_found"}

        metadata: dict[str, Any] = {"format": "ifc", "elements": [], "levels": [], "disciplines": []}
        try:
            import ifcopenshell

            model = ifcopenshell.open(str(path))
            storeys = model.by_type("IfcBuildingStorey")
            metadata["levels"] = [s.Name or s.GlobalId for s in storeys[:50]]
            metadata["element_count"] = len(model.by_type("IfcProduct"))
            metadata["schema"] = model.schema
            types = {}
            for product in model.by_type("IfcProduct")[:500]:
                t = product.is_a()
                types[t] = types.get(t, 0) + 1
            metadata["elements"] = types
        except Exception as exc:
            metadata["warning"] = str(exc)

        return {"status": "ok", "agent": self.name, "metadata": metadata}


class ScaleAgent(BaseWorkflowAgent):
    name = "scale"

    _SCALE_PATTERNS = [
        re.compile(r"1\s*:\s*(\d+)", re.I),
        re.compile(r"escala\s*(\d+)", re.I),
    ]

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        text_blob = " ".join(
            str(v)
            for v in (
                context.get("filename", ""),
                str(context.get("metadata", {})),
            )
        )
        detected = "1:100"
        for pattern in self._SCALE_PATTERNS:
            match = pattern.search(text_blob)
            if match:
                ratio = f"1:{match.group(1)}"
                if ratio in SUPPORTED_SCALES:
                    detected = ratio
                    break

        return {"status": "ok", "agent": self.name, "escala": detected}


class DrawingDetectorAgent(BaseWorkflowAgent):
    name = "drawing_detector"

    _RULES: list[tuple[str, tuple[str, ...]]] = [
        ("planta_baixa", ("planta", "pb", "pav", "layout")),
        ("corte", ("corte", "section")),
        ("fachada", ("fachada", "elevac")),
        ("detalhe", ("det", "detail")),
        ("fundacao", ("fund", "sapata", "estaca")),
        ("armadura", ("armad", "ferrag")),
        ("forma", ("forma", "concreto")),
        ("instalacao", ("inst", "hidro", "eletr")),
        ("pci", ("pci", "incendio", "sprinkler", "hidrante")),
    ]

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        name = str(context.get("filename", "")).lower()
        layers = context.get("metadata", {}).get("layers", [])
        haystack = name + " " + " ".join(str(x).lower() for x in layers)

        classification = "desenho_tecnico"
        confidence = 0.5
        best_score = 0
        for label, keywords in self._RULES:
            hits = sum(1 for k in keywords if k in haystack)
            if hits == 0:
                continue
            score = hits + (2 if label == "pci" else 0)
            if score > best_score:
                best_score = score
                classification = label
                confidence = min(0.95, 0.6 + 0.15 * hits)

        disciplina = context.get("disciplina") or self._infer_discipline(classification, haystack)
        return {
            "status": "ok",
            "agent": self.name,
            "classificacao": classification,
            "disciplina": disciplina,
            "confidence": confidence,
        }

    @staticmethod
    def _infer_discipline(classification: str, haystack: str) -> str:
        if classification == "pci" or "incendio" in haystack:
            return "incendio"
        if classification in ("fundacao", "armadura", "forma"):
            return "estrutural"
        if "eletr" in haystack:
            return "eletrica"
        if "hidro" in haystack:
            return "hidraulica"
        return "arquitetura"


class TemplateAgent(BaseWorkflowAgent):
    name = "template"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        ctx = build_sheet_context(
            empresa=context.get("empresa", "IA Server Santos"),
            autor=context.get("autor", context.get("responsavel", "")),
            crea=context.get("crea", ""),
            escala=context.get("escala", "1:100"),
            titulo=context.get("titulo", context.get("filename", "Desenho")),
            codigo=context.get("codigo", ""),
            revisao=context.get("revisao", "REV00"),
        )
        rendered = render_default_sheet(ctx)
        return {
            "status": "ok",
            "agent": self.name,
            "formato": context.get("formato", "A1"),
            "orientacao": context.get("orientacao", "paisagem"),
            "rendered_preview": rendered[:500],
            "context": ctx,
        }


class SheetAgent(BaseWorkflowAgent):
    name = "sheet"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        if db is None:
            return {"status": "skipped", "reason": "no_db"}

        project_id = uuid.UUID(str(context["project_id"]))
        sheet = WorkflowSheet(
            project_id=project_id,
            numero_prancha=context.get("numero_prancha", "01"),
            codigo_desenho=context.get("codigo", context.get("codigo_desenho", "")),
            escala=context.get("escala", "1:100"),
            disciplina=context.get("disciplina"),
            status="gerada",
            layout_json={
                "classificacao": context.get("classificacao"),
                "template_preview": context.get("rendered_preview"),
                "occupancy": context.get("occupancy", 0.72),
            },
        )
        db.add(sheet)
        db.flush()
        return {"status": "ok", "agent": self.name, "sheet_id": str(sheet.id)}


class LayoutOptimizerAgent(BaseWorkflowAgent):
    name = "layout_optimizer"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        drawings = context.get("drawings", [])
        count = max(len(drawings), 1)
        occupancy = min(0.95, 0.55 + 0.08 * count)
        return {
            "status": "ok",
            "agent": self.name,
            "occupancy": round(occupancy, 3),
            "layout_strategy": "bin_packing_greedy_v1",
        }


class RevisionAgent(BaseWorkflowAgent):
    name = "revision"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        if db is None:
            return {"status": "skipped", "reason": "no_db"}

        project_id = uuid.UUID(str(context["project_id"]))
        project = db.get(Project, project_id)
        current = project.versao_atual if project else "REV00"
        next_code = _next_revision_code(current)

        revision = WorkflowRevision(
            project_id=project_id,
            codigo=next_code,
            autor=context.get("autor"),
            descricao=context.get("descricao", "Revisão automática do workflow"),
            arquivo_origem_id=_uuid_or_none(context.get("arquivo_origem_id")),
            arquivo_destino_id=_uuid_or_none(context.get("arquivo_destino_id")),
        )
        db.add(revision)
        if project:
            project.versao_atual = next_code
        db.flush()
        return {"status": "ok", "agent": self.name, "codigo": next_code, "revision_id": str(revision.id)}


class CompareAgent(BaseWorkflowAgent):
    name = "compare"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": self.name,
            "report": {
                "added": [],
                "removed": [],
                "modified": [],
                "layers_changed": [],
                "note": "Comparador v1 — integração ODA/IfcOpenShell pendente",
            },
        }


class PublishAgent(BaseWorkflowAgent):
    name = "publish"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        from pathlib import Path

        from core.database.models import Project
        from core.database.workflow_models import WorkflowDelivery, WorkflowRevision, WorkflowSheet
        from core.workflow.publish.package_builder import build_delivery_zip, collect_local_project_files
        from core.workflow.publish.pdf_generator import generate_publication_pdf, generate_sheet_pdf
        from core.workflow.publish.stamp_audit import build_stamp_audit
        from core.workflow.storage.client import store_artifact
        from core.workflow.storage.paths import build_context_from_project

        project_id = str(context.get("project_id", ""))
        project = db.get(Project, uuid.UUID(project_id)) if db is not None else None

        meta = build_context_from_project(project, context) if project else {
            "tenant": context.get("tenant", "default"),
            "project_id": project_id,
            "discipline": context.get("disciplina", "geral"),
            "revision": context.get("revisao", "REV00"),
            "version": context.get("commit_hash", "v1"),
        }

        sheets_data: list[dict[str, Any]] = []
        if db is not None:
            rows = (
                db.query(WorkflowSheet)
                .filter(WorkflowSheet.project_id == uuid.UUID(project_id))
                .order_by(WorkflowSheet.created_at.desc())
                .limit(20)
                .all()
            )
            sheets_data = [
                {
                    "numero_prancha": r.numero_prancha,
                    "codigo_desenho": r.codigo_desenho,
                    "escala": r.escala,
                    "disciplina": r.disciplina,
                }
                for r in rows
            ]

        pub_ctx = {
            **context,
            "project_name": project.name if project else context.get("filename", "Projeto"),
            "cliente": project.cliente if project else None,
            "responsavel": project.responsavel if project else None,
            "revisao": meta["revision"],
        }

        sheet_pdf = generate_sheet_pdf(
            {**context, "stamp_audit": build_stamp_audit(pipeline="workflow_auto")}
        )
        pub_pdf = generate_publication_pdf(pub_ctx, sheets=sheets_data)

        sheet_store = store_artifact(
            **meta,
            filename=f"prancha_{context.get('numero_prancha', '01')}.pdf",
            data=sheet_pdf,
            content_type="application/pdf",
        )
        pub_store = store_artifact(
            **meta,
            filename="publicacao.pdf",
            data=pub_pdf,
            content_type="application/pdf",
        )

        project_dir = Path(__file__).resolve().parents[3] / "data" / "projects" / project_id
        zip_files: list[tuple[str, bytes]] = [
            ("Pranchas/publicacao.pdf", pub_pdf),
            (f"Pranchas/{Path(sheet_store['key']).name}", sheet_pdf),
        ]
        zip_files.extend(collect_local_project_files(project_dir))
        manifest = {
            "project_id": project_id,
            "revision": meta["revision"],
            "structure": ["Pranchas", "Memoriais", "Planilhas", "Modelos BIM", "Relatórios"],
            "artifacts": [sheet_store, pub_store],
        }
        zip_bytes = build_delivery_zip(manifest=manifest, files=zip_files)
        zip_store = store_artifact(
            **meta,
            filename="pacote_entrega.zip",
            data=zip_bytes,
            content_type="application/zip",
        )

        delivery_id = None
        revision_row = None
        if db is not None:
            revision_row = (
                db.query(WorkflowRevision)
                .filter(WorkflowRevision.project_id == uuid.UUID(project_id))
                .order_by(WorkflowRevision.created_at.desc())
                .first()
            )
            delivery = WorkflowDelivery(
                project_id=uuid.UUID(project_id),
                revision_id=revision_row.id if revision_row else None,
                package_path=zip_store["uri"],
                status="publicado",
                manifest={
                    **manifest,
                    "zip": zip_store,
                    "pdf": pub_store,
                    "sheet_pdf": sheet_store,
                },
            )
            db.add(delivery)
            db.flush()
            delivery_id = str(delivery.id)

        return {
            "status": "ok",
            "agent": self.name,
            "delivery_id": delivery_id,
            "outputs": {
                "pdf": pub_store["uri"],
                "sheet_pdf": sheet_store["uri"],
                "zip": zip_store["uri"],
                "storage_backend": pub_store["backend"],
            },
            "structure": manifest["structure"],
        }


class SignatureAgent(BaseWorkflowAgent):
    name = "signature"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        content = str(context.get("pdf_path", context.get("project_id", "")))
        digest = hashlib.sha256(content.encode()).hexdigest()
        return {
            "status": "ok",
            "agent": self.name,
            "cert_type": context.get("cert_type", "A1"),
            "hash": digest,
            "signed": False,
            "note": "Integração ICP-Brasil pendente — hash registrado",
        }


class BimAgent(BaseWorkflowAgent):
    name = "bim"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        return IfcAgent(self.llm).run(context, db)


class NotificationAgent(BaseWorkflowAgent):
    name = "notification"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": self.name,
            "channel": "in_app",
            "message": context.get("message", "Evento workflow processado"),
        }


class VersionAgent(BaseWorkflowAgent):
    name = "version"

    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        if db is None:
            return {"status": "skipped", "reason": "no_db"}
        project_id = uuid.UUID(str(context["project_id"]))
        branch = context.get("branch", "main")
        message = context.get("mensagem", "commit automático")
        snapshot = context.get("snapshot", {})
        commit_hash = hashlib.sha256(f"{project_id}:{message}".encode()).hexdigest()[:16]

        version = WorkflowVersion(
            project_id=project_id,
            branch=branch,
            tag=context.get("tag"),
            commit_hash=commit_hash,
            mensagem=message,
            snapshot=snapshot,
        )
        db.add(version)
        db.flush()
        return {"status": "ok", "agent": self.name, "commit_hash": commit_hash, "version_id": str(version.id)}


def _next_revision_code(current: str) -> str:
    match = re.match(r"REV(\d+)", current or "REV00", re.I)
    num = int(match.group(1)) + 1 if match else 1
    return f"REV{num:02d}"


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    return uuid.UUID(str(value))


def persist_drawing(
    db: Session,
    *,
    project_id: uuid.UUID,
    project_file_id: uuid.UUID | None,
    classificacao: str,
    escala: str,
    disciplina: str | None,
    metadata: dict[str, Any],
) -> WorkflowDrawing:
    drawing = WorkflowDrawing(
        project_id=project_id,
        project_file_id=project_file_id,
        classificacao=classificacao,
        escala=escala,
        disciplina=disciplina,
        metadata_json=metadata,
    )
    db.add(drawing)
    db.flush()
    return drawing


def resolve_file_agent(filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    return {
        ".dwg": "dwg",
        ".dxf": "dxf",
        ".ifc": "ifc",
        ".pdf": "pdf",
    }.get(ext)
