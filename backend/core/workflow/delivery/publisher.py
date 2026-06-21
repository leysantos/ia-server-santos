"""Publicação de pacote de entrega — estrutura GRD + pranchas PDF."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.database.models import Project
from core.database.workflow_models import (
    WorkflowDelivery,
    WorkflowDeliveryPackage,
    WorkflowPackageItem,
    WorkflowRevision,
    WorkflowSheet,
)
from core.workflow.events.bus import get_event_bus
from core.workflow.events.types import WorkflowEventType
from core.workflow.publish.grd_generator import generate_grd_pdf
from core.workflow.publish.package_builder import build_delivery_zip
from core.workflow.publish.pdf_generator import generate_sheet_pdf
from core.workflow.publish.stamp_audit import build_stamp_audit
from core.workflow.storage.client import store_artifact
from core.workflow.storage.paths import build_context_from_project
from core.workflow.template_engine.engine import build_sheet_context


class DeliveryPackagePublisher:
    """Monta ZIP profissional e registra entrega no workflow."""

    def publish(
        self,
        db: Session,
        package: WorkflowDeliveryPackage,
        items: list[WorkflowPackageItem],
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        project = db.get(Project, package.project_id)
        if not project:
            return {"status": "error", "reason": "project_not_found"}

        selected = [i for i in items if i.selected]
        if not selected:
            return {"status": "error", "reason": "no_items_selected"}

        empresa_nome = "IA Server Santos"
        if package.empresa_id:
            from core.database.workflow_models import Company

            company = db.get(Company, package.empresa_id)
            if company:
                empresa_nome = company.nome

        zip_files: list[tuple[str, bytes]] = []
        grd_items: list[dict[str, Any]] = []
        sheets_created = 0
        revisions_created = 0

        for idx, item in enumerate(sorted(selected, key=lambda x: x.sort_order), start=1):
            pf = item.project_file
            if not pf:
                continue

            source_path = Path(pf.storage_path)
            codigo = item.codigo_aprovado or item.codigo_sugerido or pf.filename
            ext = Path(pf.filename).suffix.lower()
            arcname = f"{item.pasta_destino}/{item.arquivo_final or codigo + ext}"

            grd_items.append(
                {
                    "codigo_aprovado": codigo,
                    "arquivo_final": item.arquivo_final or f"{codigo}{ext}",
                    "disciplina_codigo": item.disciplina_codigo,
                    "disciplina": item.disciplina,
                    "pasta_destino": item.pasta_destino,
                    "filename": pf.filename,
                }
            )

            if item.role == "prancha":
                sheet_ctx = build_sheet_context(
                    empresa=empresa_nome,
                    autor=project.responsavel or "",
                    crea="",
                    escala=item.escala or "1:100",
                    titulo=item.titulo or codigo,
                    codigo=codigo,
                    revisao=item.revisao_documento or package.codigo_emissao,
                )
                analysis = item.analysis_json if isinstance(item.analysis_json, dict) else {}
                stamp_audit = build_stamp_audit(analysis_json=analysis, pipeline="workflow_wizard")
                pdf_ctx = {
                    **sheet_ctx,
                    "formato": item.formato or package.formato_padrao,
                    "orientacao": package.orientacao_padrao,
                    "classificacao": item.tipo_desenho,
                    "filename": pf.filename,
                    "analysis_json": analysis,
                    "stamp_audit": stamp_audit,
                }
                sheet_pdf = generate_sheet_pdf(pdf_ctx)
                pdf_arc = f"{item.pasta_destino}/{codigo}.pdf"
                zip_files.append((pdf_arc, sheet_pdf))

                sheet = WorkflowSheet(
                    project_id=package.project_id,
                    template_id=package.template_id,
                    numero_prancha=f"{item.folha_numero:02d}" if item.folha_numero else "01",
                    codigo_desenho=codigo,
                    escala=item.escala,
                    disciplina=item.disciplina,
                    status="publicada",
                    layout_json={
                        "package_id": str(package.id),
                        "item_id": str(item.id),
                        "stamp_audit": stamp_audit,
                    },
                )
                db.add(sheet)
                sheets_created += 1

                revision = WorkflowRevision(
                    project_id=package.project_id,
                    codigo=package.codigo_emissao,
                    autor=project.responsavel,
                    descricao=f"Emissão {codigo} — pacote {package.titulo}",
                    arquivo_origem_id=pf.id,
                )
                db.add(revision)
                revisions_created += 1

            if source_path.exists():
                zip_files.append((arcname, source_path.read_bytes()))
            item.status = "published"

        grd_pdf = generate_grd_pdf(
            project_name=project.name,
            project_codigo=project.codigo,
            cliente=project.cliente,
            codigo_emissao=package.codigo_emissao,
            responsavel=project.responsavel,
            items=grd_items,
        )
        zip_files.append((f"GRD_{package.codigo_emissao}.pdf", grd_pdf))

        manifest = {
            "package_id": str(package.id),
            "project_id": str(package.project_id),
            "codigo_emissao": package.codigo_emissao,
            "titulo": package.titulo,
            "formato_padrao": package.formato_padrao,
            "structure": package.structure_preview,
            "items": grd_items,
            "total_items": len(grd_items),
        }
        zip_bytes = build_delivery_zip(manifest=manifest, files=zip_files)

        meta = build_context_from_project(
            project,
            {
                "disciplina": project.disciplina or "geral",
                "revisao": package.codigo_emissao,
                "commit_hash": str(package.id)[:8],
            },
        )
        zip_store = store_artifact(
            **meta,
            filename=f"entrega_{package.codigo_emissao}.zip",
            data=zip_bytes,
            content_type="application/zip",
        )
        grd_store = store_artifact(
            **meta,
            filename=f"GRD_{package.codigo_emissao}.pdf",
            data=grd_pdf,
            content_type="application/pdf",
        )

        delivery = WorkflowDelivery(
            project_id=package.project_id,
            package_path=zip_store["uri"],
            status="publicado",
            manifest={
                **manifest,
                "zip": zip_store,
                "pdf": grd_store,
                "grd": grd_store,
                "tipo": "wizard_package",
            },
        )
        db.add(delivery)
        db.flush()

        project.versao_atual = package.codigo_emissao
        package.status = "published"
        package.package_path = zip_store["uri"]
        package.manifest = manifest
        package.published_delivery_id = delivery.id
        package.structure_preview = self._build_structure_preview(selected)

        bus = get_event_bus()
        bus.publish(
            WorkflowEventType.DELIVERY_COMPLETED,
            {
                "package_id": str(package.id),
                "delivery_id": str(delivery.id),
                "codigo_emissao": package.codigo_emissao,
                "items": len(selected),
            },
            project_id=str(package.project_id),
            actor=actor,
            db=db,
        )

        db.flush()
        return {
            "status": "ok",
            "delivery_id": str(delivery.id),
            "package_id": str(package.id),
            "sheets_created": sheets_created,
            "revisions_created": revisions_created,
            "zip": zip_store,
            "grd": grd_store,
            "total_items": len(selected),
        }

    @staticmethod
    def _build_structure_preview(items: list[WorkflowPackageItem]) -> dict[str, list[str]]:
        tree: dict[str, list[str]] = {}
        for item in items:
            folder = item.pasta_destino or "OUTROS"
            tree.setdefault(folder, [])
            name = item.arquivo_final or item.codigo_aprovado or item.titulo or "arquivo"
            tree[folder].append(name)
        return tree
