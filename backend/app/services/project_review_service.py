"""Orquestração do Project Review Engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.workspace_service import PROJECTS_DATA_DIR
from core.project_review.budget_analysis import analyze_budget
from core.project_review.compatibilization import analyze_compatibility
from core.project_review.constants import ReviewStatus
from core.project_review.digital_twin import build_twin_snapshot
from core.project_review.ingestion_pipeline import IngestionPipeline
from core.project_review.memorial_analysis import analyze_memorial
from core.project_review.nc_engine import compare_nc_versions, nc_from_agent_payload
from core.project_review.report_generator import (
    build_memorial_docx,
    build_nc_report_docx,
    build_review_report_docx,
    build_technical_opinion_docx,
    build_tdr_docx,
)
from core.project_review.repository import ProjectReviewRepository
from core.project_review.review_agent import ProjectReviewAgent
from core.project_review.scoring_engine import compute_scores
from core.project_review.vision_analysis_service import extract_analysis
from core.project_review.workflow import can_transition, next_status_after_analysis
from core.runtime.review_guard import assert_review_can_start
from core.runtime.job_tracking import track_sync_job


class ProjectReviewService:
    def __init__(self) -> None:
        self.agent = ProjectReviewAgent()

    def list_reviews(self, project_id: str, db: Session) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        pid = self._parse_uuid(project_id)
        if not repo.get_project(pid):
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        items = [ProjectReviewRepository.review_to_dict(r) for r in repo.list_reviews(pid)]
        return {"total": len(items), "items": items}

    def get_review(self, project_id: str, review_id: str, db: Session) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        review = repo.get_review(self._parse_uuid(review_id))
        if not review or str(review.project_id) != project_id:
            raise HTTPException(status_code=404, detail="Revisão não encontrada")
        return ProjectReviewRepository.review_to_dict(review)

    def start_review(
        self,
        project_id: str,
        *,
        parent_review_id: str | None,
        enable_vision: bool,
        db: Session,
    ) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        pid = self._parse_uuid(project_id)
        project = repo.get_project(pid)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")

        assert_review_can_start(project_id)

        parent_uuid = self._parse_uuid(parent_review_id) if parent_review_id else None
        review = repo.create_review(
            pid,
            parent_review_id=parent_uuid,
            status=ReviewStatus.EM_PROCESSAMENTO.value,
        )
        repo.update_review(review, started_at=datetime.now(timezone.utc))
        db.commit()

        existing_by_file = {
            str(ext.project_file_id): ext for ext in repo.list_extractions(pid)
        }

        with track_sync_job(
            kind="review",
            label=f"Revisão técnica v{review.version}",
            project_id=project_id,
        ) as review_job:
            review_job.update(phase="ingest", message="Ingestão de documentos…")

            pipeline = IngestionPipeline(enable_vision=enable_vision)
            extraction_rows: list[dict[str, Any]] = []

            project_dir = PROJECTS_DATA_DIR / project_id

            for pf in project.files:
                file_path = Path(pf.storage_path)
                if not file_path.is_file():
                    alt = project_dir / pf.filename
                    if alt.is_file():
                        file_path = alt
                    else:
                        continue

                cached = existing_by_file.get(str(pf.id))
                processed = pipeline.process_file(
                    file_path,
                    pf.filename,
                    existing_vision_json=cached.vision_json if cached else None,
                )
                repo.save_extraction(
                    project_id=pid,
                    project_file_id=pf.id,
                    discipline=processed.get("discipline"),
                    format_key=processed.get("format_key", "unknown"),
                    extraction_json=processed.get("extraction_json"),
                    vision_json=processed.get("vision_json"),
                )
                extraction_rows.append(
                    {
                        "file_id": str(pf.id),
                        "filename": pf.filename,
                        "discipline": processed.get("discipline"),
                        "format_key": processed.get("format_key"),
                        "extraction_json": processed.get("extraction_json"),
                        "vision_json": processed.get("vision_json"),
                    }
                )

            review_job.update(phase="analysis", message="Agente de revisão…")

            normas = []
            for row in extraction_rows:
                vis = extract_analysis(row.get("vision_json"))
                normas.extend(vis.get("normas_aplicaveis") or [])

            twin_snapshot = build_twin_snapshot(
                project_id=project_id,
                extractions=extraction_rows,
                normas=sorted(set(normas)),
                version=review.version,
            )
            twin = repo.save_digital_twin(pid, twin_snapshot)

            compat = analyze_compatibility(twin_snapshot)
            budget = analyze_budget(
                twin_payload=twin_snapshot,
                extraction_items=extraction_rows,
            )
            memorial = analyze_memorial(extraction_rows)

            analysis = self.agent.analyze(
                project_name=project.name,
                twin_payload=twin_snapshot,
                extractions=extraction_rows,
            )

            ncs_data = analysis.get("nao_conformidades") or []
            nc_records = [
                nc_from_agent_payload(
                    nc,
                    project_id=pid,
                    review_id=review.id,
                    index=i,
                )
                for i, nc in enumerate(ncs_data, start=1)
            ]
            if nc_records:
                repo.bulk_create_ncs(nc_records)

            scores = compute_scores(
                analysis=analysis,
                nonconformities=nc_records,
                compat_report=compat,
                budget_report=budget,
            )

            report_payload = {
                "compatibilizacao": compat,
                "orcamento": budget,
                "memorial": memorial,
                "digital_twin_id": str(twin.id),
            }

            status = next_status_after_analysis(has_ncs=bool(nc_records), scores=scores)
            repo.update_review(
                review,
                status=status,
                scores=scores,
                analysis_payload=analysis,
                report_payload=report_payload,
                completed_at=datetime.now(timezone.utc),
            )
            db.commit()

        result = ProjectReviewRepository.review_to_dict(review)
        result["ncs_created"] = len(nc_records)
        result["files_processed"] = len(extraction_rows)
        result["vision_cached_files"] = sum(
            1
            for pf in project.files
            if existing_by_file.get(str(pf.id)) and existing_by_file[str(pf.id)].vision_json
        )
        return result

    def update_review_status(
        self,
        project_id: str,
        review_id: str,
        status: str,
        db: Session,
    ) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        review = repo.get_review(self._parse_uuid(review_id))
        if not review or str(review.project_id) != project_id:
            raise HTTPException(status_code=404, detail="Revisão não encontrada")
        if not can_transition(review.status, status):
            raise HTTPException(
                status_code=400,
                detail=f"Transição inválida: {review.status} → {status}",
            )
        repo.update_review(review, status=status)
        db.commit()
        return ProjectReviewRepository.review_to_dict(review)

    def list_ncs(
        self,
        project_id: str,
        review_id: str | None,
        db: Session,
    ) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        pid = self._parse_uuid(project_id)
        rid = self._parse_uuid(review_id) if review_id else None
        items = [
            ProjectReviewRepository.nc_to_dict(nc)
            for nc in repo.list_ncs(pid, review_id=rid)
        ]
        return {"total": len(items), "items": items}

    def update_nc_status(
        self,
        project_id: str,
        nc_id: str,
        status: str,
        db: Session,
    ) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        from core.database.models import ProjectNonconformity

        nc = db.get(ProjectNonconformity, self._parse_uuid(nc_id))
        if not nc or str(nc.project_id) != project_id:
            raise HTTPException(status_code=404, detail="NC não encontrada")
        nc.status = status
        db.commit()
        return ProjectReviewRepository.nc_to_dict(nc)

    def get_digital_twin(self, project_id: str, db: Session) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        twin = repo.latest_digital_twin(self._parse_uuid(project_id))
        if not twin:
            raise HTTPException(status_code=404, detail="Digital twin não encontrado")
        return ProjectReviewRepository.twin_to_dict(twin)

    def list_extractions(self, project_id: str, db: Session) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        rows = repo.list_extractions(self._parse_uuid(project_id))
        items = [
            {
                "id": str(r.id),
                "project_file_id": str(r.project_file_id),
                "discipline": r.discipline,
                "format_key": r.format_key,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
            }
            for r in rows
        ]
        return {"total": len(items), "items": items}

    def dashboard(self, project_id: str | None, db: Session) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        pid = self._parse_uuid(project_id) if project_id else None
        stats = repo.dashboard_stats(pid)
        latest = repo.latest_review(pid) if pid else None
        pending = 0
        if pid:
            pending = sum(
                1 for nc in repo.list_ncs(pid) if nc.status in ("aberta", "em_correcao")
            )
        return {
            "project_id": project_id,
            "reviews_total": stats["reviews_total"],
            "ncs_total": stats["ncs_total"],
            "latest_review": ProjectReviewRepository.review_to_dict(latest) if latest else None,
            "scores": latest.scores if latest else None,
            "pending_ncs": pending,
        }

    def compare_versions(
        self,
        project_id: str,
        v1_id: str,
        v2_id: str,
        db: Session,
    ) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        r1 = repo.get_review(self._parse_uuid(v1_id))
        r2 = repo.get_review(self._parse_uuid(v2_id))
        if not r1 or not r2 or str(r1.project_id) != project_id or str(r2.project_id) != project_id:
            raise HTTPException(status_code=404, detail="Revisões não encontradas")

        nc1 = [ProjectReviewRepository.nc_to_dict(n) for n in repo.list_ncs(r1.project_id, review_id=r1.id)]
        nc2 = [ProjectReviewRepository.nc_to_dict(n) for n in repo.list_ncs(r2.project_id, review_id=r2.id)]
        return {
            "v1_review_id": v1_id,
            "v2_review_id": v2_id,
            "comparison": compare_nc_versions(nc1, nc2),
        }

    def export_report(
        self,
        project_id: str,
        review_id: str,
        report_type: str,
        db: Session,
    ) -> tuple[bytes, str]:
        repo = ProjectReviewRepository(db)
        project = repo.get_project(self._parse_uuid(project_id))
        review = repo.get_review(self._parse_uuid(review_id))
        if not project or not review or str(review.project_id) != project_id:
            raise HTTPException(status_code=404, detail="Revisão não encontrada")

        analysis = review.analysis_payload or {}
        scores = review.scores or {}
        ncs = [
            ProjectReviewRepository.nc_to_dict(n)
            for n in repo.list_ncs(review.project_id, review_id=review.id)
        ]
        review_dict = ProjectReviewRepository.review_to_dict(review)

        if report_type == "review":
            content = build_review_report_docx(
                project_name=project.name,
                review=review_dict,
                scores=scores,
                nonconformities=ncs,
                analysis=analysis,
            )
            filename = f"revisao_tecnica_v{review.version}.docx"
        elif report_type == "nc":
            content = build_nc_report_docx(project_name=project.name, nonconformities=ncs)
            filename = f"nao_conformidades_v{review.version}.docx"
        elif report_type == "parecer":
            content = build_technical_opinion_docx(project_name=project.name, analysis=analysis)
            filename = f"parecer_tecnico_v{review.version}.docx"
        elif report_type == "tdr":
            content = build_tdr_docx(project_name=project.name)
            filename = f"termo_referencia_{project.name[:30]}.docx"
        elif report_type.startswith("memorial:"):
            discipline = report_type.split(":", 1)[1]
            twin = repo.latest_digital_twin(review.project_id)
            payload = twin.payload if twin else {}
            content = build_memorial_docx(
                project_name=project.name,
                discipline=discipline,
                twin_payload={"payload": payload},
            )
            filename = f"memorial_{discipline}_v{review.version}.docx"
        else:
            raise HTTPException(status_code=400, detail=f"Tipo de relatório inválido: {report_type}")

        return content, filename

    @staticmethod
    def _parse_uuid(value: str | None) -> uuid.UUID:
        if not value:
            raise HTTPException(status_code=400, detail="UUID inválido")
        try:
            return uuid.UUID(str(value))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="UUID inválido") from exc
