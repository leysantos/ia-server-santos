"""Serviço de aplicação — Workflow Projetos."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.database.models import Project
from core.database.workflow_models import (
    Company,
    ProjectFolder,
    WorkflowDelivery,
    WorkflowDrawing,
    WorkflowEvent,
    WorkflowJob,
    WorkflowRevision,
    WorkflowSheet,
    WorkflowVersion,
)
from core.workflow.orchestrator import get_workflow_orchestrator
from core.workflow.workers.dispatcher import (
    enqueue_process_file,
    enqueue_process_project,
    serialize_job,
)


class WorkflowService:
    def get_dashboard(self, db: Session, *, company_id: str | None = None) -> dict[str, Any]:
        q_projects = db.query(Project)
        if company_id:
            q_projects = q_projects.filter(Project.empresa_id == uuid.UUID(company_id))

        active = q_projects.filter(Project.status == "ativo").count()
        files_processed = db.query(WorkflowDrawing).count()
        sheets = db.query(WorkflowSheet).count()
        open_revisions = db.query(WorkflowRevision).count()
        recent_events = (
            db.query(WorkflowEvent)
            .order_by(WorkflowEvent.created_at.desc())
            .limit(20)
            .all()
        )
        recent_publications = (
            db.query(WorkflowDelivery)
            .order_by(WorkflowDelivery.created_at.desc())
            .limit(10)
            .all()
        )

        return {
            "projetos_ativos": active,
            "arquivos_processados": files_processed,
            "pranchas_geradas": sheets,
            "revisoes_registradas": open_revisions,
            "publicacoes_recentes": len(recent_publications),
            "eventos_recentes": [self._serialize_event(e) for e in recent_events],
        }

    def get_project_workflow(self, project_id: str, db: Session) -> dict[str, Any]:
        from core.database.models import ProjectFile

        project = self._get_project(project_id, db)
        pid = uuid.UUID(project_id)

        project_files = db.query(ProjectFile).filter(ProjectFile.project_id == pid).all()
        file_map = {str(f.id): f.filename for f in project_files}

        folders = (
            db.query(ProjectFolder)
            .filter(ProjectFolder.project_id == pid)
            .order_by(ProjectFolder.sort_order)
            .all()
        )
        events = (
            db.query(WorkflowEvent)
            .filter(WorkflowEvent.project_id == pid)
            .order_by(WorkflowEvent.created_at.desc())
            .limit(50)
            .all()
        )
        drawings = db.query(WorkflowDrawing).filter(WorkflowDrawing.project_id == pid).all()
        sheets = db.query(WorkflowSheet).filter(WorkflowSheet.project_id == pid).all()
        revisions = (
            db.query(WorkflowRevision)
            .filter(WorkflowRevision.project_id == pid)
            .order_by(WorkflowRevision.created_at.desc())
            .all()
        )
        versions = (
            db.query(WorkflowVersion)
            .filter(WorkflowVersion.project_id == pid)
            .order_by(WorkflowVersion.created_at.desc())
            .limit(20)
            .all()
        )
        deliveries = (
            db.query(WorkflowDelivery)
            .filter(WorkflowDelivery.project_id == pid)
            .order_by(WorkflowDelivery.created_at.desc())
            .limit(10)
            .all()
        )
        jobs = (
            db.query(WorkflowJob)
            .filter(WorkflowJob.project_id == pid)
            .order_by(WorkflowJob.created_at.desc())
            .limit(10)
            .all()
        )

        drawing_rows = [self._serialize_drawing(d, file_map) for d in drawings]
        pranchas_count = sum(1 for d in drawing_rows if d.get("tipo_arquivo") == "prancha")
        docs_count = sum(1 for d in drawing_rows if d.get("tipo_arquivo") == "documento")

        from core.workflow.classification.file_classifier import classify_project_file
        from pathlib import Path

        inventory = []
        for pf in project_files:
            ext = Path(pf.filename).suffix.lower()
            if ext not in {".pdf", ".dwg", ".dxf", ".ifc"}:
                continue
            kind = classify_project_file(pf.filename)
            processed = any(str(d.project_file_id) == str(pf.id) for d in drawings)
            inventory.append(
                {
                    "file_id": str(pf.id),
                    "filename": pf.filename,
                    "tipo_arquivo": kind["tipo_arquivo"],
                    "subtipo": kind["subtipo"],
                    "pipeline": kind["pipeline"],
                    "processed": processed,
                }
            )

        return {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "codigo": project.codigo,
                "cliente": project.cliente,
                "responsavel": project.responsavel,
                "disciplina": project.disciplina,
                "status": project.status,
                "versao_atual": project.versao_atual,
                "workflow_initialized": project.workflow_initialized,
                "empresa_id": str(project.empresa_id) if project.empresa_id else None,
            },
            "folders": [self._serialize_folder(f) for f in folders],
            "summary": {
                "total_arquivos": len(project_files),
                "arquivos_suportados": len(inventory),
                "pranchas": pranchas_count,
                "documentos": docs_count,
                "pranchas_geradas": len(sheets),
                "revisoes": len(revisions),
                "entregas": len(deliveries),
            },
            "inventory": inventory,
            "drawings": drawing_rows,
            "sheets": [self._serialize_sheet(s) for s in sheets],
            "revisions": [self._serialize_revision(r) for r in revisions],
            "versions": [self._serialize_version(v) for v in versions],
            "events": [self._serialize_event(e) for e in events],
            "deliveries": [self._serialize_delivery(d) for d in deliveries],
            "jobs": [serialize_job(j) for j in jobs],
        }

    def initialize_project(self, project_id: str, db: Session, *, empresa_id: str | None = None) -> dict:
        self._get_project(project_id, db)
        orchestrator = get_workflow_orchestrator()
        result = orchestrator.initialize_project(project_id, db, empresa_id=empresa_id)
        db.commit()
        return result

    def process_project(
        self, project_id: str, db: Session, *, sync: bool = False, force: bool = False
    ) -> dict:
        self._get_project(project_id, db)
        from config.settings import get_settings

        settings = get_settings()
        if settings.workflow_async_upload and not sync:
            return enqueue_process_project(db, project_id, sync=sync)
        orchestrator = get_workflow_orchestrator()
        result = orchestrator.run_full_pipeline(project_id, db, force=force)
        db.commit()
        return {"mode": "sync", **result}

    def process_file(
        self,
        project_id: str,
        file_id: str,
        db: Session,
        *,
        sync: bool = False,
        force: bool = False,
    ) -> dict:
        from core.database.models import ProjectFile
        from config.settings import get_settings

        self._get_project(project_id, db)
        pf = db.get(ProjectFile, uuid.UUID(file_id))
        if not pf or str(pf.project_id) != project_id:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado no projeto")

        settings = get_settings()
        if settings.workflow_async_upload and not sync:
            return enqueue_process_file(db, project_id, file_id, sync=sync)

        orchestrator = get_workflow_orchestrator()
        result = orchestrator.process_file(project_id, pf, db, force=force)
        db.commit()
        return {"mode": "sync", **result}

    def get_job(self, job_id: str, db: Session) -> dict:
        row = db.get(WorkflowJob, uuid.UUID(job_id))
        if not row:
            raise HTTPException(status_code=404, detail="Job não encontrado")
        return serialize_job(row)

    def list_project_jobs(self, project_id: str, db: Session, limit: int = 20) -> dict:
        pid = uuid.UUID(project_id)
        rows = (
            db.query(WorkflowJob)
            .filter(WorkflowJob.project_id == pid)
            .order_by(WorkflowJob.created_at.desc())
            .limit(limit)
            .all()
        )
        return {"total": len(rows), "items": [serialize_job(r) for r in rows]}

    def update_project_metadata(
        self,
        project_id: str,
        db: Session,
        *,
        codigo: Optional[str] = None,
        cliente: Optional[str] = None,
        responsavel: Optional[str] = None,
        disciplina: Optional[str] = None,
        status: Optional[str] = None,
        empresa_id: Optional[str] = None,
    ) -> dict:
        project = self._get_project(project_id, db)
        if codigo is not None:
            project.codigo = codigo
        if cliente is not None:
            project.cliente = cliente
        if responsavel is not None:
            project.responsavel = responsavel
        if disciplina is not None:
            project.disciplina = disciplina
        if status is not None:
            project.status = status
        if empresa_id is not None:
            project.empresa_id = uuid.UUID(empresa_id) if empresa_id else None
        db.commit()
        return {"updated": True, "project_id": project_id}

    def list_companies(self, db: Session) -> dict:
        rows = db.query(Company).order_by(Company.nome).all()
        return {
            "total": len(rows),
            "items": [
                {
                    "id": str(c.id),
                    "nome": c.nome,
                    "slug": c.slug,
                    "logo_path": c.logo_path,
                    "ativo": c.ativo,
                }
                for c in rows
            ],
        }

    def create_company(self, db: Session, *, nome: str, slug: str) -> dict:
        existing = db.query(Company).filter(Company.slug == slug).first()
        if existing:
            raise HTTPException(status_code=409, detail="Slug já existe")
        company = Company(nome=nome, slug=slug)
        db.add(company)
        db.commit()
        return {"id": str(company.id), "nome": company.nome, "slug": company.slug}

    @staticmethod
    def _get_project(project_id: str, db: Session) -> Project:
        project = db.get(Project, uuid.UUID(project_id))
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        return project

    @staticmethod
    def _serialize_event(row: WorkflowEvent) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "event_type": row.event_type,
            "payload": row.payload,
            "actor": row.actor,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _serialize_folder(row: ProjectFolder) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "nome": row.nome,
            "path": row.path,
            "disciplina": row.disciplina,
            "sort_order": row.sort_order,
        }

    @staticmethod
    def _serialize_drawing(
        row: WorkflowDrawing,
        file_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        meta = row.metadata_json or {}
        tipo = meta.get("tipo_arquivo")
        if not tipo:
            tipo = "documento" if row.escala == "—" else "prancha"
        fid = str(row.project_file_id) if row.project_file_id else None
        return {
            "id": str(row.id),
            "classificacao": row.classificacao,
            "escala": row.escala,
            "disciplina": row.disciplina,
            "project_file_id": fid,
            "filename": file_map.get(fid or "", meta.get("filename")),
            "tipo_arquivo": tipo,
            "subtipo": meta.get("subtipo", row.classificacao),
        }

    @staticmethod
    def _serialize_sheet(row: WorkflowSheet) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "numero_prancha": row.numero_prancha,
            "codigo_desenho": row.codigo_desenho,
            "escala": row.escala,
            "disciplina": row.disciplina,
            "status": row.status,
        }

    @staticmethod
    def _serialize_revision(row: WorkflowRevision) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "codigo": row.codigo,
            "autor": row.autor,
            "descricao": row.descricao,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _serialize_version(row: WorkflowVersion) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "branch": row.branch,
            "tag": row.tag,
            "commit_hash": row.commit_hash,
            "mensagem": row.mensagem,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _serialize_delivery(row: WorkflowDelivery) -> dict[str, Any]:
        from core.workflow.storage.client import artifact_download_path

        manifest = row.manifest or {}
        pdf_info = manifest.get("pdf") if isinstance(manifest.get("pdf"), dict) else {}
        zip_info = manifest.get("zip") if isinstance(manifest.get("zip"), dict) else {}
        pdf_key = pdf_info.get("key")
        zip_key = zip_info.get("key")
        return {
            "id": str(row.id),
            "status": row.status,
            "package_path": row.package_path,
            "pdf_uri": pdf_info.get("uri"),
            "pdf_key": pdf_key,
            "pdf_download_url": artifact_download_path(pdf_key) if pdf_key else None,
            "zip_uri": zip_info.get("uri") or row.package_path,
            "zip_key": zip_key,
            "zip_download_url": artifact_download_path(zip_key) if zip_key else None,
            "storage_backend": pdf_info.get("backend") or zip_info.get("backend"),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
