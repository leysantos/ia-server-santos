"""Serviço de domínio — Wizard de Entrega (Fase 3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from core.database.models import Project, ProjectFile
from core.database.workflow_models import (
    CompanyStamp,
    WorkflowDeliveryPackage,
    WorkflowPackageItem,
    WorkflowTemplate,
)
from core.workflow.agents.specialists import _next_revision_code
from core.workflow.delivery.analyzer import DeliveryPackageAnalyzer
from core.workflow.delivery.publisher import DeliveryPackagePublisher
from core.workflow.nomenclature.standards import SHEET_FORMATS
from core.workflow.seed.defaults import ensure_default_sheet_templates


class DeliveryWizardService:
    def __init__(self) -> None:
        self.analyzer = DeliveryPackageAnalyzer()
        self.publisher = DeliveryPackagePublisher()

    def list_sheet_templates(self, db: Session) -> dict[str, Any]:
        ensure_default_sheet_templates(db)
        db.commit()
        rows = (
            db.query(WorkflowTemplate)
            .filter(WorkflowTemplate.ativo.is_(True))
            .order_by(WorkflowTemplate.formato, WorkflowTemplate.nome)
            .all()
        )
        return {
            "formatos": list(SHEET_FORMATS),
            "items": [self._serialize_template(t) for t in rows],
        }

    def list_stamps(self, db: Session, *, empresa_id: str | None = None) -> dict[str, Any]:
        q = db.query(CompanyStamp).order_by(CompanyStamp.nome)
        if empresa_id:
            q = q.filter(CompanyStamp.company_id == uuid.UUID(empresa_id))
        rows = q.all()
        return {
            "items": [
                {
                    "id": str(s.id),
                    "nome": s.nome,
                    "image_path": s.image_path,
                    "posicao": s.posicao,
                    "company_id": str(s.company_id),
                }
                for s in rows
            ]
        }

    def list_packages(self, project_id: str, db: Session) -> dict[str, Any]:
        pid = uuid.UUID(project_id)
        rows = (
            db.query(WorkflowDeliveryPackage)
            .filter(WorkflowDeliveryPackage.project_id == pid)
            .order_by(WorkflowDeliveryPackage.created_at.desc())
            .all()
        )
        return {
            "total": len(rows),
            "items": [self._serialize_package_summary(p) for p in rows],
        }

    def create_package(self, project_id: str, db: Session, *, titulo: str | None = None) -> dict[str, Any]:
        project = self._get_project(project_id, db)
        ensure_default_sheet_templates(db)

        next_rev = _next_revision_code(project.versao_atual or "REV00")
        pkg = WorkflowDeliveryPackage(
            project_id=project.id,
            status="draft",
            titulo=titulo or f"Entrega {next_rev} — {project.name}",
            codigo_emissao=next_rev,
            formato_padrao="A1",
            orientacao_padrao="paisagem",
            empresa_id=project.empresa_id,
        )
        db.add(pkg)
        db.flush()

        files = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == project.id)
            .order_by(ProjectFile.created_at)
            .all()
        )
        for idx, pf in enumerate(files):
            db.add(
                WorkflowPackageItem(
                    package_id=pkg.id,
                    project_file_id=pf.id,
                    selected=False,
                    sort_order=idx,
                    status="pending",
                )
            )
        db.flush()
        db.commit()
        return self.get_package(project_id, str(pkg.id), db)

    def get_package(self, project_id: str, package_id: str, db: Session) -> dict[str, Any]:
        pkg = self._get_package(project_id, package_id, db)
        files = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == pkg.project_id)
            .order_by(ProjectFile.created_at)
            .all()
        )
        return {
            "package": self._serialize_package(pkg),
            "items": [self._serialize_item(i) for i in pkg.items],
            "available_files": [
                {"id": str(f.id), "filename": f.filename, "created_at": f.created_at.isoformat() if f.created_at else None}
                for f in files
            ],
            "structure_preview": pkg.structure_preview or self._preview_structure(pkg.items),
            "norm_gaps": self._compute_norm_gaps(pkg, db),
        }

    @staticmethod
    def _compute_norm_gaps(pkg: WorkflowDeliveryPackage, db: Session) -> dict[str, Any]:
        from core.knowledge.norm_packs.project_gaps import (
            compute_project_norm_gaps,
            disciplines_from_package_items,
        )

        project = db.get(Project, pkg.project_id)
        disciplines = disciplines_from_package_items(
            pkg.items,
            project_discipline=project.disciplina if project else None,
            selected_only=True,
        )
        if not disciplines and project and project.disciplina:
            disciplines = [project.disciplina]
        if not disciplines:
            disciplines = ["geral"]
        return compute_project_norm_gaps(disciplines)

    def update_package(
        self,
        project_id: str,
        package_id: str,
        db: Session,
        *,
        titulo: str | None = None,
        codigo_emissao: str | None = None,
        formato_padrao: str | None = None,
        orientacao_padrao: str | None = None,
        template_id: str | None = None,
        stamp_id: str | None = None,
        observacoes: str | None = None,
    ) -> dict[str, Any]:
        pkg = self._get_package(project_id, package_id, db)
        if pkg.status == "published":
            raise ValueError("Pacote já publicado — crie nova emissão")

        if titulo is not None:
            pkg.titulo = titulo
        if codigo_emissao is not None:
            pkg.codigo_emissao = codigo_emissao
        if formato_padrao is not None:
            pkg.formato_padrao = formato_padrao
        if orientacao_padrao is not None:
            pkg.orientacao_padrao = orientacao_padrao
        if template_id is not None:
            pkg.template_id = uuid.UUID(template_id) if template_id else None
        if stamp_id is not None:
            pkg.stamp_id = uuid.UUID(stamp_id) if stamp_id else None
        if observacoes is not None:
            pkg.observacoes = observacoes

        db.commit()
        return self.get_package(project_id, package_id, db)

    def update_selection(
        self,
        project_id: str,
        package_id: str,
        db: Session,
        *,
        file_ids: list[str],
    ) -> dict[str, Any]:
        pkg = self._get_package(project_id, package_id, db)
        selected_ids = {uuid.UUID(fid) for fid in file_ids}
        existing = {item.project_file_id: item for item in pkg.items}

        for pf_id, item in existing.items():
            item.selected = pf_id in selected_ids

        project = db.get(Project, pkg.project_id)
        all_files = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == pkg.project_id)
            .order_by(ProjectFile.created_at)
            .all()
        )
        for idx, pf in enumerate(all_files):
            if pf.id not in existing:
                db.add(
                    WorkflowPackageItem(
                        package_id=pkg.id,
                        project_file_id=pf.id,
                        selected=pf.id in selected_ids,
                        sort_order=idx,
                        status="pending",
                    )
                )
        db.commit()
        return self.get_package(project_id, package_id, db)

    def analyze_package(self, project_id: str, package_id: str, db: Session) -> dict[str, Any]:
        pkg = self._get_package(project_id, package_id, db)
        selected_items = [i for i in pkg.items if i.selected]
        if not selected_items:
            raise ValueError("Selecione ao menos um arquivo para análise")

        file_ids = [i.project_file_id for i in selected_items]
        proposals = self.analyzer.analyze_files(
            db,
            pkg.project_id,
            file_ids,
            revisao_emissao=pkg.codigo_emissao,
            formato_padrao=pkg.formato_padrao,
        )
        proposal_map = {p["project_file_id"]: p for p in proposals}

        for item in pkg.items:
            prop = proposal_map.get(str(item.project_file_id))
            if not prop or not item.selected:
                continue
            item.role = prop["role"]
            item.disciplina = prop["disciplina"]
            item.disciplina_codigo = prop["disciplina_codigo"]
            item.folha_numero = prop["folha_numero"]
            item.tipo_desenho = prop["tipo_desenho"]
            item.titulo = prop["titulo"]
            item.codigo_sugerido = prop["codigo_sugerido"]
            item.codigo_aprovado = prop["codigo_aprovado"]
            item.arquivo_final = prop["arquivo_final"]
            item.formato = prop["formato"]
            item.escala = prop["escala"]
            item.pasta_destino = prop["pasta_destino"]
            item.revisao_documento = prop["revisao_documento"]
            item.analysis_json = prop.get("analysis")
            item.status = "ready"

        pkg.status = "ready"
        pkg.structure_preview = self._preview_structure([i for i in pkg.items if i.selected])
        db.commit()
        return self.get_package(project_id, package_id, db)

    def update_item(
        self,
        project_id: str,
        package_id: str,
        item_id: str,
        db: Session,
        **fields: Any,
    ) -> dict[str, Any]:
        pkg = self._get_package(project_id, package_id, db)
        item = self._get_item(pkg, item_id)

        for key in (
            "selected",
            "codigo_aprovado",
            "formato",
            "escala",
            "titulo",
            "pasta_destino",
            "folha_numero",
        ):
            if key in fields and fields[key] is not None:
                setattr(item, key, fields[key])

        if fields.get("codigo_aprovado"):
            ext = "." + (item.arquivo_final or "").split(".")[-1] if item.arquivo_final and "." in item.arquivo_final else ".pdf"
            if item.project_file:
                ext = __import__("pathlib").Path(item.project_file.filename).suffix or ext
            item.arquivo_final = f"{fields['codigo_aprovado']}{ext}"

        pkg.structure_preview = self._preview_structure([i for i in pkg.items if i.selected])
        db.commit()
        return self.get_package(project_id, package_id, db)

    def publish_package(self, project_id: str, package_id: str, db: Session) -> dict[str, Any]:
        pkg = (
            db.query(WorkflowDeliveryPackage)
            .options(joinedload(WorkflowDeliveryPackage.items).joinedload(WorkflowPackageItem.project_file))
            .filter(
                WorkflowDeliveryPackage.id == uuid.UUID(package_id),
                WorkflowDeliveryPackage.project_id == uuid.UUID(project_id),
            )
            .first()
        )
        if not pkg:
            raise ValueError("Pacote não encontrado")
        if pkg.status == "published":
            raise ValueError("Pacote já publicado")

        ready = [i for i in pkg.items if i.selected and i.status in ("ready", "approved", "pending")]
        if not ready:
            raise ValueError("Execute a análise IA antes de publicar")

        for item in ready:
            if not item.codigo_aprovado and item.codigo_sugerido:
                item.codigo_aprovado = item.codigo_sugerido
            item.status = "approved"

        result = self.publisher.publish(db, pkg, pkg.items)
        pkg.published_at = datetime.now(timezone.utc)
        db.commit()
        return {
            **result,
            "package": self._serialize_package(pkg),
        }

    @staticmethod
    def _get_project(project_id: str, db: Session) -> Project:
        project = db.get(Project, uuid.UUID(project_id))
        if not project:
            raise ValueError("Projeto não encontrado")
        return project

    @staticmethod
    def _get_package(project_id: str, package_id: str, db: Session) -> WorkflowDeliveryPackage:
        pkg = (
            db.query(WorkflowDeliveryPackage)
            .options(joinedload(WorkflowDeliveryPackage.items).joinedload(WorkflowPackageItem.project_file))
            .filter(
                WorkflowDeliveryPackage.id == uuid.UUID(package_id),
                WorkflowDeliveryPackage.project_id == uuid.UUID(project_id),
            )
            .first()
        )
        if not pkg:
            raise ValueError("Pacote não encontrado")
        return pkg

    @staticmethod
    def _get_item(pkg: WorkflowDeliveryPackage, item_id: str) -> WorkflowPackageItem:
        for item in pkg.items:
            if str(item.id) == item_id:
                return item
        raise ValueError("Item não encontrado")

    @staticmethod
    def _preview_structure(items: list[WorkflowPackageItem]) -> dict[str, list[str]]:
        tree: dict[str, list[str]] = {}
        for item in items:
            if not item.selected:
                continue
            folder = item.pasta_destino or "OUTROS"
            name = item.arquivo_final or item.codigo_aprovado or item.titulo or "arquivo"
            tree.setdefault(folder, []).append(name)
        return tree

    @staticmethod
    def _serialize_template(row: WorkflowTemplate) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "nome": row.nome,
            "formato": row.formato,
            "orientacao": row.orientacao,
            "disciplina": row.disciplina,
            "company_id": str(row.company_id) if row.company_id else None,
        }

    @staticmethod
    def _serialize_package_summary(row: WorkflowDeliveryPackage) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "titulo": row.titulo,
            "status": row.status,
            "codigo_emissao": row.codigo_emissao,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }

    @staticmethod
    def _serialize_package(row: WorkflowDeliveryPackage) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "status": row.status,
            "titulo": row.titulo,
            "codigo_emissao": row.codigo_emissao,
            "formato_padrao": row.formato_padrao,
            "orientacao_padrao": row.orientacao_padrao,
            "template_id": str(row.template_id) if row.template_id else None,
            "stamp_id": str(row.stamp_id) if row.stamp_id else None,
            "empresa_id": str(row.empresa_id) if row.empresa_id else None,
            "observacoes": row.observacoes,
            "package_path": row.package_path,
            "published_delivery_id": str(row.published_delivery_id) if row.published_delivery_id else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }

    @staticmethod
    def _serialize_item(row: WorkflowPackageItem) -> dict[str, Any]:
        pf = row.project_file
        return {
            "id": str(row.id),
            "project_file_id": str(row.project_file_id),
            "filename": pf.filename if pf else None,
            "selected": row.selected,
            "role": row.role,
            "disciplina": row.disciplina,
            "disciplina_codigo": row.disciplina_codigo,
            "folha_numero": row.folha_numero,
            "tipo_desenho": row.tipo_desenho,
            "titulo": row.titulo,
            "codigo_sugerido": row.codigo_sugerido,
            "codigo_aprovado": row.codigo_aprovado,
            "arquivo_final": row.arquivo_final,
            "formato": row.formato,
            "escala": row.escala,
            "pasta_destino": row.pasta_destino,
            "revisao_documento": row.revisao_documento,
            "sort_order": row.sort_order,
            "status": row.status,
            "analysis": row.analysis_json,
        }


_delivery_wizard: DeliveryWizardService | None = None


def get_delivery_wizard_service() -> DeliveryWizardService:
    global _delivery_wizard
    if _delivery_wizard is None:
        _delivery_wizard = DeliveryWizardService()
    return _delivery_wizard
