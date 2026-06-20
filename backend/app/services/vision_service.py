"""Serviço de análise visual — workspace/projetos (Vision Engine)."""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from pathlib import Path
from typing import Any, Iterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.workspace_service import PROJECTS_DATA_DIR
from core.database.connection import session_scope
from core.project_review.report_generator import (
    build_correcoes_report_docx,
    build_memorial_docx,
    build_nc_report_docx,
    build_photographic_report_docx,
    build_review_report_docx,
    build_site_inspection_laudo_docx,
    build_tdr_docx,
    build_technical_opinion_docx,
    build_vision_technical_report_docx,
)
from core.project_review.repository import ProjectReviewRepository
from core.project_review.vision_analysis_service import (
    VisionAnalysisService,
    extract_analysis,
    extract_technical_report,
    is_visual_file,
)
from core.project_review.vision_prompts import VisionAnalysisMode
from core.stream_events import format_sse
from core.vision_engine.workspace_status import check_workspace_tools

logger = logging.getLogger(__name__)

VISION_REPORT_TYPES = frozenset(
    {
        "relatorio_fotografico",
        "laudo",
        "correcoes",
        "tecnico",
        "review",
        "nc",
        "parecer",
        "memorial",
        "tdr",
    }
)


class VisionService:
    def __init__(self) -> None:
        self.vision = VisionAnalysisService()

    def get_status(self) -> dict[str, Any]:
        status = self.vision.check_availability()
        status["modes"] = self.vision.list_modes()
        status["technical_model"] = status.get("technical_model") or "qwen3:14b"
        return status

    def get_workspace_status(self) -> dict[str, Any]:
        return check_workspace_tools()

    def list_analyses(self, project_id: str, db: Session) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        pid = self._parse_uuid(project_id)
        if not repo.get_project(pid):
            raise HTTPException(status_code=404, detail="Projeto não encontrado")

        items: list[dict[str, Any]] = []
        for ext in repo.list_extractions(pid):
            if not ext.vision_json:
                continue
            pf = ext.project_file
            items.append(self._row_from_extraction(ext, pf.filename if pf else "—"))

        return {"total": len(items), "items": items}

    def analyze(
        self,
        project_id: str,
        *,
        file_ids: list[str],
        mode: str,
        extra_context: str,
        db: Session,
    ) -> dict[str, Any]:
        repo = ProjectReviewRepository(db)
        pid = self._parse_uuid(project_id)
        project = repo.get_project(pid)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")

        if mode not in {m.value for m in VisionAnalysisMode}:
            raise HTTPException(status_code=400, detail=f"Modo inválido: {mode}")

        availability = self.vision.check_availability()
        if not availability.get("available"):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Visão indisponível. Modelo multimodal necessário: "
                    f"{availability.get('primary', 'gemma3:12b')}. "
                    f"{availability.get('error') or ''}"
                ).strip(),
            )

        targets = self._resolve_files(project, file_ids)
        if not targets:
            raise HTTPException(
                status_code=400,
                detail="Nenhum arquivo visual (PNG, JPG, PDF…) encontrado no projeto.",
            )

        results = self._run_analysis_batch(
            repo, pid, project, targets, mode=mode, extra_context=extra_context
        )
        db.commit()
        summary = self.vision.aggregate_report_summary(results)
        try:
            from core.project_memory.service import record_vision_completion

            record_vision_completion(
                project_id=project_id,
                mode=mode,
                analyzed=summary["analyzed"],
                total=summary["total"],
                errors=summary["errors"],
                db=db,
            )
        except Exception:
            pass
        return {
            "project_id": project_id,
            "mode": mode,
            "total": summary["total"],
            "analyzed": summary["analyzed"],
            "errors": summary["errors"],
            "skipped": summary["skipped"],
            "items": [self._public_item(r) for r in results],
            "summary": summary,
        }

    def analyze_stream_events(
        self,
        project_id: str,
        *,
        file_ids: list[str],
        mode: str,
        extra_context: str,
    ) -> Iterator[str]:
        """Gera eventos SSE (progress / file_done / done / error) durante análise em lote."""
        q: queue.Queue[tuple[str, Any]] = queue.Queue()

        def worker() -> None:
            try:
                with session_scope() as db:
                    repo = ProjectReviewRepository(db)
                    pid = self._parse_uuid(project_id)
                    project = repo.get_project(pid)
                    if not project:
                        q.put(("error", {"error": "Projeto não encontrado"}))
                        return

                    if mode not in {m.value for m in VisionAnalysisMode}:
                        q.put(("error", {"error": f"Modo inválido: {mode}"}))
                        return

                    availability = self.vision.check_availability()
                    if not availability.get("available"):
                        q.put(
                            (
                                "error",
                                {
                                    "error": (
                                        "Visão indisponível. Instale gemma3:12b no Ollama."
                                    )
                                },
                            )
                        )
                        return

                    targets = self._resolve_files(project, file_ids)
                    if not targets:
                        q.put(("error", {"error": "Nenhum arquivo visual encontrado."}))
                        return

                    total = len(targets)
                    results: list[dict[str, Any]] = []
                    step_frac = {
                        "prepare": 0.02,
                        "ocr": 0.10,
                        "vision": 0.55,
                        "technical": 0.88,
                        "save": 0.96,
                    }

                    def pct(idx: int, step: str) -> int:
                        frac = (idx + step_frac.get(step, 0.05)) / total
                        return min(99, round(frac * 100))

                    for idx, (pf, path) in enumerate(targets):
                        file_id = str(pf.id)
                        fname = pf.filename

                        def emit(phase: str, message: str) -> None:
                            q.put(
                                (
                                    "progress",
                                    {
                                        "phase": phase,
                                        "current": idx + 1,
                                        "total": total,
                                        "percent": pct(idx, phase),
                                        "message": message,
                                        "filename": fname,
                                        "file_id": file_id,
                                    },
                                )
                            )

                        emit("prepare", f"Preparando {fname}…")

                        def on_step(data: dict[str, Any]) -> None:
                            emit(data.get("phase", "vision"), data.get("message", fname))

                        row = self.vision.pipeline.run(
                            path,
                            mode=mode,
                            extra_context=extra_context,
                            filename=fname,
                            on_progress=on_step,
                        )
                        row["project_file_id"] = file_id

                        emit("save", f"Salvando {fname}…")
                        self._persist_analysis_row(repo, pid, project, pf, row)
                        results.append(row)

                        q.put(("file_done", {"item": self._public_item(row)}))
                        q.put(
                            (
                                "progress",
                                {
                                    "phase": "file_complete",
                                    "current": idx + 1,
                                    "total": total,
                                    "percent": min(99, round((idx + 1) / total * 100)),
                                    "message": f"Concluído: {fname}",
                                    "filename": fname,
                                    "file_id": file_id,
                                },
                            )
                        )

                    summary = self.vision.aggregate_report_summary(results)
                    try:
                        from core.project_memory.service import record_vision_completion

                        record_vision_completion(
                            project_id=project_id,
                            mode=mode,
                            analyzed=summary["analyzed"],
                            total=summary["total"],
                            errors=summary["errors"],
                            db=db,
                        )
                    except Exception:
                        pass
                    q.put(
                        (
                            "done",
                            {
                                "project_id": project_id,
                                "mode": mode,
                                "total": summary["total"],
                                "analyzed": summary["analyzed"],
                                "errors": summary["errors"],
                                "skipped": summary["skipped"],
                                "items": [self._public_item(r) for r in results],
                                "summary": summary,
                            },
                        )
                    )
            except Exception as exc:
                logger.exception("Vision analyze stream falhou")
                q.put(("error", {"error": str(exc)}))

        threading.Thread(target=worker, daemon=True).start()

        while True:
            kind, payload = q.get()
            if kind == "progress":
                yield format_sse("progress", payload)
            elif kind == "file_done":
                yield format_sse("file_done", payload)
            elif kind == "done":
                yield format_sse("done", payload)
                break
            elif kind == "error":
                yield format_sse("error", payload)
                break

    def _run_analysis_batch(
        self,
        repo: ProjectReviewRepository,
        pid: uuid.UUID,
        project,
        targets: list[tuple[Any, Path]],
        *,
        mode: str,
        extra_context: str,
    ) -> list[dict[str, Any]]:
        batch_input: list[tuple[Path, str, str]] = []
        for pf, path in targets:
            batch_input.append((path, pf.filename, str(pf.id)))

        results = self.vision.analyze_batch(batch_input, mode=mode, extra_context=extra_context)

        for row in results:
            fid = row.get("project_file_id")
            if not fid:
                continue
            pf_uuid = self._parse_uuid(fid)
            pf = next((f for f in project.files if f.id == pf_uuid), None)
            if not pf:
                continue
            self._persist_analysis_row(repo, pid, project, pf, row)

        return results

    def _persist_analysis_row(self, repo, pid, project, pf, row: dict[str, Any]) -> None:
        ext_data = extract_analysis(row)
        existing_ext = next(
            (e for e in repo.list_extractions(pid) if e.project_file_id == pf.id),
            None,
        )
        repo.save_extraction(
            project_id=pid,
            project_file_id=pf.id,
            discipline=ext_data.get("disciplina") or (existing_ext.discipline if existing_ext else None),
            format_key=Path(pf.filename).suffix.lstrip(".") or "unknown",
            extraction_json=row.get("ocr") or (existing_ext.extraction_json if existing_ext else {}),
            vision_json=row,
        )

    def export_report(
        self,
        project_id: str,
        *,
        report_type: str,
        file_ids: list[str],
        obra_info: str,
        solicitante: str,
        objeto: str,
        discipline: str,
        prazo: str,
        db: Session,
    ) -> tuple[bytes, str]:
        repo = ProjectReviewRepository(db)
        pid = self._parse_uuid(project_id)
        project = repo.get_project(pid)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")

        if report_type not in VISION_REPORT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"report_type inválido. Opções: {', '.join(sorted(VISION_REPORT_TYPES))}",
            )

        analyses = self._collect_analyses(repo, pid, file_ids)
        summary = self.vision.aggregate_report_summary(analyses) if analyses else {}
        safe_name = project.name.replace(" ", "_")[:40]

        if report_type in ("review", "nc", "parecer", "tdr") or report_type.startswith("memorial"):
            return self._export_review_family(
                repo,
                pid,
                project,
                report_type,
                discipline,
                safe_name,
                db,
            )

        if not analyses:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma análise visual encontrada. Execute a análise antes de exportar.",
            )

        if report_type == "relatorio_fotografico":
            content = build_photographic_report_docx(
                project_name=project.name,
                analyses=analyses,
                summary=summary,
                obra_info=obra_info,
            )
            return content, f"relatorio_fotografico_{safe_name}.docx"

        if report_type == "laudo":
            content = build_site_inspection_laudo_docx(
                project_name=project.name,
                analyses=analyses,
                summary=summary,
                solicitante=solicitante,
                objeto=objeto or project.description or "",
            )
            return content, f"laudo_vistoria_{safe_name}.docx"

        if report_type == "correcoes":
            content = build_correcoes_report_docx(
                project_name=project.name,
                analyses=analyses,
                summary=summary,
                prazo=prazo,
            )
            return content, f"relatorio_correcoes_{safe_name}.docx"

        if report_type == "tecnico":
            content = build_vision_technical_report_docx(
                project_name=project.name,
                analyses=analyses,
                summary=summary,
            )
            return content, f"relatorio_tecnico_{safe_name}.docx"

        raise HTTPException(status_code=400, detail="Tipo de relatório não suportado")

    def _export_review_family(
        self,
        repo: ProjectReviewRepository,
        pid: uuid.UUID,
        project,
        report_type: str,
        discipline: str,
        safe_name: str,
        db: Session,
    ) -> tuple[bytes, str]:
        reviews = repo.list_reviews(pid)
        if not reviews:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma revisão técnica encontrada. Inicie uma revisão em /projects/{id}/review.",
            )
        latest = reviews[0]
        review_dict = {
            "version": latest.version,
            "status": latest.status,
            "id": str(latest.id),
        }
        analysis = latest.analysis_payload or {}
        scores = (latest.scores or {}) if hasattr(latest, "scores") else {}
        ncs = [self._nc_to_dict(nc) for nc in repo.list_ncs(pid, review_id=latest.id)]
        twin = repo.latest_digital_twin(pid)
        twin_payload = twin.payload if twin else {}

        if report_type == "review":
            content = build_review_report_docx(
                project_name=project.name,
                review=review_dict,
                scores=scores if isinstance(scores, dict) else {},
                nonconformities=ncs,
                analysis=analysis if isinstance(analysis, dict) else {},
            )
            return content, f"revisao_{safe_name}.docx"

        if report_type == "nc":
            content = build_nc_report_docx(project_name=project.name, nonconformities=ncs)
            return content, f"ncs_{safe_name}.docx"

        if report_type == "parecer":
            content = build_technical_opinion_docx(
                project_name=project.name,
                analysis=analysis if isinstance(analysis, dict) else {},
            )
            return content, f"parecer_{safe_name}.docx"

        if report_type == "tdr":
            content = build_tdr_docx(
                project_name=project.name,
                scope=project.description or "",
            )
            return content, f"tdr_{safe_name}.docx"

        if report_type == "memorial":
            disc = discipline or "geral"
            content = build_memorial_docx(
                project_name=project.name,
                discipline=disc,
                twin_payload=twin_payload if isinstance(twin_payload, dict) else {},
            )
            return content, f"memorial_{disc}_{safe_name}.docx"

        raise HTTPException(status_code=400, detail="Tipo de relatório inválido")

    def _collect_analyses(
        self,
        repo: ProjectReviewRepository,
        project_id: uuid.UUID,
        file_ids: list[str],
    ) -> list[dict[str, Any]]:
        id_set = {str(self._parse_uuid(fid)) for fid in file_ids} if file_ids else None
        rows: list[dict[str, Any]] = []
        for ext in repo.list_extractions(project_id):
            if not ext.vision_json:
                continue
            if id_set and str(ext.project_file_id) not in id_set:
                continue
            pf = ext.project_file
            rows.append(
                {
                    **ext.vision_json,
                    "project_file_id": str(ext.project_file_id),
                    "filename": pf.filename if pf else "—",
                }
            )
        return rows

    def _resolve_files(self, project, file_ids: list[str]):
        id_set = {self._parse_uuid(fid) for fid in file_ids} if file_ids else None
        project_dir = PROJECTS_DATA_DIR / str(project.id)
        resolved: list[tuple[Any, Path]] = []

        for pf in project.files:
            if id_set and pf.id not in id_set:
                continue
            path = Path(pf.storage_path)
            if not path.is_file():
                alt = project_dir / pf.filename
                if alt.is_file():
                    path = alt
                else:
                    continue
            if not is_visual_file(path):
                continue
            resolved.append((pf, path))

        return resolved

    @staticmethod
    def _nc_to_dict(nc) -> dict[str, Any]:
        return {
            "codigo": nc.codigo,
            "categoria": nc.categoria,
            "criticidade": nc.criticidade,
            "descricao": nc.descricao,
            "evidencia": nc.evidencia,
            "norma": nc.norma,
            "impacto": nc.impacto,
            "recomendacao": nc.recomendacao,
            "status": nc.status,
        }

    @staticmethod
    def _row_from_extraction(ext, filename: str) -> dict[str, Any]:
        payload = ext.vision_json or {}
        return {
            "project_file_id": str(ext.project_file_id),
            "filename": filename,
            "analysis_mode": payload.get("analysis_mode", "—"),
            "analyzer": payload.get("analyzer"),
            "skipped": bool(payload.get("skipped")),
            "error": payload.get("error"),
            "model_used": payload.get("model_used"),
            "technical_model_used": payload.get("technical_model_used"),
            "analyzed_at": payload.get("analyzed_at"),
            "analysis": extract_analysis(payload) or payload.get("analysis"),
            "technical_report": extract_technical_report(payload),
        }

    @staticmethod
    def _public_item(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "project_file_id": row.get("project_file_id", ""),
            "filename": row.get("filename", ""),
            "analysis_mode": row.get("analysis_mode", ""),
            "analyzer": row.get("analyzer"),
            "skipped": bool(row.get("skipped")),
            "error": row.get("error"),
            "model_used": row.get("model_used"),
            "technical_model_used": row.get("technical_model_used"),
            "analyzed_at": row.get("analyzed_at"),
            "analysis": row.get("analysis"),
            "technical_report": row.get("technical_report"),
        }

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID:
        try:
            return uuid.UUID(str(value))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="ID inválido") from exc
