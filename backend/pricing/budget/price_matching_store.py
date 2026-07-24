"""Persistência de jobs e linhas de lançamento de preços."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.database.connection import is_db_enabled
from core.database.models import BudgetPriceMatching, BudgetPriceMatchingJob
from pricing.budget.price_matching_hierarchy import ImportRowKind, ImportedBudgetLine
from pricing.budget.price_matching_import import ImportedPriceRow
from pricing.budget.price_matching_service import PriceMatchingService

_memory_lock = threading.Lock()
_memory_jobs: dict[str, dict[str, Any]] = {}
_progress_lock = threading.Lock()
_job_progress: dict[str, dict[str, int]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _set_job_progress(job_id: str, processed: int, total: int) -> None:
    with _progress_lock:
        _job_progress[job_id] = {"processed": max(0, processed), "total": max(0, total)}


def _clear_job_progress(job_id: str) -> None:
    with _progress_lock:
        _job_progress.pop(job_id, None)


def _attach_process_progress(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = str(payload.get("id") or "")
    total = int(payload.get("rows_total") or 0)
    processed = 0
    status = str(payload.get("status") or "")
    if status == "done" and total > 0:
        payload["rows_processed"] = total
        payload["process_percent"] = 100.0
        return payload
    with _progress_lock:
        prog = _job_progress.get(job_id)
        if prog:
            processed = int(prog.get("processed") or 0)
            total = int(prog.get("total") or total)
    payload["rows_processed"] = processed
    payload["process_percent"] = round(100.0 * processed / total, 1) if total else 0.0
    return payload


class PriceMatchingStore:
    def create_job(
        self,
        db: Session | None,
        *,
        title: str = "Lançar Preços",
        bdi: float = 0.0,
        increase_index: float = 1.0,
        uf: str = "AM",
        cliente: str | None = None,
        obra: str | None = None,
        source_filename: str | None = None,
        source_format: str | None = None,
        user_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
        budget_document_id: uuid.UUID | None = None,
        session_id: str | None = None,
        hierarchy: list[dict[str, Any]] | None = None,
        price_bases: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4()
        if is_db_enabled() and db is not None:
            job = BudgetPriceMatchingJob(
                id=job_id,
                title=title,
                status="draft",
                bdi=bdi,
                increase_index=increase_index,
                uf=uf.upper(),
                cliente=cliente,
                obra=obra,
                source_filename=source_filename,
                source_format=source_format,
                user_id=user_id,
                empresa_id=empresa_id,
                budget_document_id=budget_document_id,
                session_id=session_id,
                hierarchy=hierarchy,
                price_bases=price_bases,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job.to_dict()

        payload = {
            "id": str(job_id),
            "title": title,
            "status": "draft",
            "bdi": bdi,
            "increase_index": increase_index,
            "uf": uf.upper(),
            "cliente": cliente,
            "obra": obra,
            "source_filename": source_filename,
            "source_format": source_format,
            "budget_document_id": str(budget_document_id) if budget_document_id else None,
            "session_id": session_id,
            "hierarchy": hierarchy or [],
            "price_bases": price_bases or [],
            "user_id": str(user_id) if user_id else None,
            "empresa_id": str(empresa_id) if empresa_id else None,
            "rows_total": 0,
            "rows_matched": 0,
            "rows": [],
            "created_at": _utcnow().isoformat(),
            "updated_at": _utcnow().isoformat(),
            "processed_at": None,
            "model_used": None,
        }
        with _memory_lock:
            _memory_jobs[payload["id"]] = payload
        return {k: v for k, v in payload.items() if k != "rows"}

    def add_import_rows(
        self,
        db: Session | None,
        job_id: str,
        rows: list[ImportedPriceRow | ImportedBudgetLine],
        *,
        usuario: str | None = None,
        row_type_default: str = ImportRowKind.SERVICO.value,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if is_db_enabled() and db is not None:
            jid = uuid.UUID(job_id)
            for row in rows:
                rt = getattr(row, "row_type", row_type_default) or row_type_default
                codigo = str(getattr(row, "codigo", "") or "").strip()
                rec = BudgetPriceMatching(
                    job_id=jid,
                    row_index=row.row_index,
                    row_type=rt,
                    item=row.item,
                    descricao_original=row.descricao,
                    unidade=row.unidade,
                    quantidade=row.quantidade,
                    codigo_base=codigo or None,
                    status="pending",
                    usuario=usuario,
                )
                db.add(rec)
                out.append(rec.to_dict())
            job = db.get(BudgetPriceMatchingJob, jid)
            if job:
                job.rows_total = len(rows)
                job.status = "imported"
                job.updated_at = _utcnow()
            db.commit()
            rows_db = (
                db.query(BudgetPriceMatching)
                .filter_by(job_id=jid)
                .order_by(BudgetPriceMatching.row_index)
                .all()
            )
            return [r.to_dict() for r in rows_db]

        with _memory_lock:
            job = _memory_jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            job_rows = []
            for row in rows:
                rid = str(uuid.uuid4())
                rt = getattr(row, "row_type", row_type_default) or row_type_default
                codigo = str(getattr(row, "codigo", "") or "").strip()
                payload = {
                    "id": rid,
                    "job_id": job_id,
                    "row_index": row.row_index,
                    "row_type": rt,
                    "item": row.item,
                    "descricao_original": row.descricao,
                    "unidade": row.unidade,
                    "quantidade": row.quantidade,
                    "codigo_base": codigo or None,
                    "status": "pending",
                    "usuario": usuario,
                    "candidates": [],
                }
                job_rows.append(payload)
            job["rows"] = job_rows
            job["rows_total"] = len(job_rows)
            job["status"] = "imported"
            job["updated_at"] = _utcnow().isoformat()
            return list(job_rows)

    def get_job(self, db: Session | None, job_id: str) -> dict[str, Any] | None:
        if is_db_enabled() and db is not None:
            jid = uuid.UUID(job_id)
            job = db.get(BudgetPriceMatchingJob, jid)
            if not job:
                return None
            rows = (
                db.query(BudgetPriceMatching)
                .filter_by(job_id=jid)
                .order_by(BudgetPriceMatching.row_index)
                .all()
            )
            payload = job.to_dict()
            payload["rows"] = [r.to_dict() for r in rows]
            return _attach_process_progress(payload)

        with _memory_lock:
            job = _memory_jobs.get(job_id)
            if not job:
                return None
            return _attach_process_progress(dict(job))

    def update_job_meta(
        self,
        db: Session | None,
        job_id: str,
        *,
        bdi: float | None = None,
        increase_index: float | None = None,
        cliente: str | None = None,
        obra: str | None = None,
        uf: str | None = None,
        status: str | None = None,
        price_bases: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if is_db_enabled() and db is not None:
            jid = uuid.UUID(job_id)
            job = db.get(BudgetPriceMatchingJob, jid)
            if not job:
                return None
            if bdi is not None:
                job.bdi = bdi
            if increase_index is not None:
                job.increase_index = increase_index
            if cliente is not None:
                job.cliente = cliente
            if obra is not None:
                job.obra = obra
            if uf is not None:
                job.uf = uf.upper()
            if status is not None:
                job.status = status
            if price_bases is not None:
                job.price_bases = price_bases
            job.updated_at = _utcnow()
            db.commit()
            return self.get_job(db, job_id)

        with _memory_lock:
            job = _memory_jobs.get(job_id)
            if not job:
                return None
            if bdi is not None:
                job["bdi"] = bdi
            if increase_index is not None:
                job["increase_index"] = increase_index
            if cliente is not None:
                job["cliente"] = cliente
            if obra is not None:
                job["obra"] = obra
            if uf is not None:
                job["uf"] = uf.upper()
            if status is not None:
                job["status"] = status
            if price_bases is not None:
                job["price_bases"] = price_bases
            job["updated_at"] = _utcnow().isoformat()
            return dict(job)

    def process_job(
        self,
        db: Session | None,
        job_id: str,
        *,
        use_llm: bool = True,
        usuario: str | None = None,
    ) -> dict[str, Any]:
        job = self.get_job(db, job_id)
        if not job:
            raise KeyError(job_id)

        self.update_job_meta(db, job_id, status="processing")
        rows = job.get("rows") or []
        total_rows = len(rows)
        _set_job_progress(job_id, 0, total_rows)
        uf = str(job.get("uf") or "AM")
        increase_index = float(job.get("increase_index") or 1.0)
        price_bases = job.get("price_bases") or None
        service = PriceMatchingService(uf=uf, use_llm=use_llm, price_bases=price_bases)
        matched = 0
        model_used: str | None = None
        now = _utcnow()

        try:
            for row_index, row in enumerate(rows, start=1):
                desc = str(row.get("descricao_original") or "")
                unit = str(row.get("unidade") or "")
                qty = float(row.get("quantidade") or 0)
                imported_code = str(row.get("codigo_base") or "").strip() or None
                existing_base = str(row.get("base") or "").strip() or None

                result = service.match_row(
                    desc,
                    unit,
                    qty,
                    imported_code=imported_code,
                    existing_base=existing_base,
                )
                priced = service.apply_pricing(result, qty, increase_index=increase_index)
                if not priced.get("codigo_base") and imported_code:
                    retry = service.match_row(
                        desc,
                        unit,
                        qty,
                        existing_base=existing_base,
                    )
                    retry_priced = service.apply_pricing(retry, qty, increase_index=increase_index)
                    if retry_priced.get("codigo_base"):
                        priced = retry_priced
                if result.model_used:
                    model_used = result.model_used
                elif priced.get("modelo_utilizado"):
                    model_used = priced.get("modelo_utilizado")
                if priced.get("codigo_base"):
                    matched += 1
                self._update_row(db, job_id, row["id"], priced, usuario=usuario, processed_at=now)
                _set_job_progress(job_id, row_index, total_rows)
                with _memory_lock:
                    mem = _memory_jobs.get(job_id)
                    if mem:
                        mem["rows_processed"] = row_index
                        mem["process_percent"] = (
                            round(100.0 * row_index / total_rows, 1) if total_rows else 0.0
                        )
        finally:
            _clear_job_progress(job_id)

        self.update_job_meta(db, job_id, status="done")
        if is_db_enabled() and db is not None:
            jid = uuid.UUID(job_id)
            job_rec = db.get(BudgetPriceMatchingJob, jid)
            if job_rec:
                job_rec.rows_matched = matched
                job_rec.model_used = model_used
                job_rec.processed_at = now
                db.commit()

        final_job = self.get_job(db, job_id) or {}
        from pricing.budget.price_matching_budget import sync_hierarchy_codes_from_rows

        final_job = sync_hierarchy_codes_from_rows(final_job)
        self.save_job_hierarchy(db, job_id, final_job.get("hierarchy"))

        if final_job.get("session_id"):
            try:
                from pricing.budget.price_matching_budget import sync_and_persist_job_budget

                sync_and_persist_job_budget(db, final_job)
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    "Falha ao sincronizar/persistir preços do job %s", job_id
                )

        with _memory_lock:
            mem = _memory_jobs.get(job_id)
            if mem:
                mem["rows_matched"] = matched
                mem["model_used"] = model_used
                mem["processed_at"] = now.isoformat()
                mem["status"] = "done"

        return _attach_process_progress(final_job)

    def _update_row(
        self,
        db: Session | None,
        job_id: str,
        row_id: str,
        payload: dict[str, Any],
        *,
        usuario: str | None = None,
        processed_at: datetime | None = None,
    ) -> None:
        if is_db_enabled() and db is not None:
            rid = uuid.UUID(row_id)
            row = db.get(BudgetPriceMatching, rid)
            if not row:
                return
            row.base = payload.get("base") if payload.get("base") is not None else row.base
            if payload.get("codigo_base") is not None:
                row.codigo_base = payload.get("codigo_base")
            row.descricao_base = payload.get("descricao_base")
            row.valor_unitario = payload.get("valor_unitario")
            row.valor_total = payload.get("valor_total")
            row.score_confianca = payload.get("score_confianca")
            row.match_level = payload.get("match_level")
            row.status = payload.get("status") or row.status
            row.modelo_utilizado = payload.get("modelo_utilizado")
            row.reference = payload.get("reference")
            row.candidates = payload.get("candidates")
            if usuario:
                row.usuario = usuario
            row.data_processamento = processed_at or _utcnow()
            row.updated_at = _utcnow()
            db.commit()
            return

        with _memory_lock:
            job = _memory_jobs.get(job_id)
            if not job:
                return
            for row in job.get("rows") or []:
                if row.get("id") == row_id:
                    merged = dict(row)
                    merged.update(payload)
                    if payload.get("codigo_base") is None and row.get("codigo_base"):
                        merged["codigo_base"] = row.get("codigo_base")
                    if payload.get("base") is None and row.get("base"):
                        merged["base"] = row.get("base")
                    row.clear()
                    row.update(merged)
                    if usuario:
                        row["usuario"] = usuario
                    row["data_processamento"] = (processed_at or _utcnow()).isoformat()
                    break

    def accept_row(self, db: Session | None, job_id: str, row_id: str) -> dict[str, Any] | None:
        return self._set_row_status(db, job_id, row_id, "accepted")

    def replace_row(
        self,
        db: Session | None,
        job_id: str,
        row_id: str,
        *,
        base: str,
        code: str,
        reference: str | None = None,
        uf: str = "AM",
        increase_index: float = 1.0,
        quantity: float | None = None,
        description: str | None = None,
        unit: str | None = None,
        price: float | None = None,
        source: str | None = None,
    ) -> dict[str, Any] | None:
        from pricing.budget.price_matching_catalog import CatalogEntry, search_catalog

        job = self.get_job(db, job_id)
        price_bases = job.get("price_bases") if job else None
        uf_val = str(job.get("uf") or uf or "AM").upper()
        entry: CatalogEntry | None = None

        if price is not None and float(price) >= 0:
            family = base.upper()
            entry = CatalogEntry(
                base=family,
                source=(source or base).lower(),
                reference=reference or "",
                code=code,
                description=description or code,
                unit=unit or "",
                price=float(price),
                default_uf=uf_val,
            )
        else:
            hits = search_catalog(
                "",
                code=code,
                base=base,
                limit=5,
                uf=uf_val,
                price_bases=price_bases,
            )
            if not hits:
                hits = search_catalog(
                    code,
                    base=base,
                    limit=5,
                    uf=uf_val,
                    price_bases=price_bases,
                )
            if reference:
                ref_hits = [h for h in hits if h.reference == reference]
                if ref_hits:
                    hits = ref_hits
            if hits:
                entry = hits[0]

        if not entry:
            return None
        qty = quantity if quantity is not None else 0.0
        if job and quantity is None:
            for row in job.get("rows") or []:
                if row.get("id") == row_id:
                    qty = float(row.get("quantidade") or 0)
                    break
        unit_adj = float(entry.price) * float(increase_index or 1.0)
        payload = {
            "base": entry.base,
            "codigo_base": entry.code,
            "descricao_base": entry.description,
            "reference": reference or entry.reference,
            "valor_unitario": round(unit_adj, 4),
            "valor_unitario_base": round(float(entry.price or 0), 4),
            "valor_total": round(unit_adj * qty, 2),
            "score_confianca": 1.0,
            "match_level": "manual",
            "status": "accepted",
        }
        self._update_row(db, job_id, row_id, payload)
        job = self.get_job(db, job_id)
        if not job:
            return None
        for row in job.get("rows") or []:
            if row.get("id") == row_id:
                return row
        return None

    def _set_row_status(self, db: Session | None, job_id: str, row_id: str, status: str) -> dict[str, Any] | None:
        if is_db_enabled() and db is not None:
            rid = uuid.UUID(row_id)
            row = db.get(BudgetPriceMatching, rid)
            if not row:
                return None
            row.status = status
            row.updated_at = _utcnow()
            db.commit()
            return row.to_dict()

        with _memory_lock:
            job = _memory_jobs.get(job_id)
            if not job:
                return None
            for row in job.get("rows") or []:
                if row.get("id") == row_id:
                    row["status"] = status
                    return dict(row)
        return None


    def save_job_hierarchy(
        self,
        db: Session | None,
        job_id: str,
        hierarchy: list[dict[str, Any]] | None,
    ) -> None:
        if not hierarchy:
            return
        if is_db_enabled() and db is not None:
            jid = uuid.UUID(job_id)
            job = db.get(BudgetPriceMatchingJob, jid)
            if job:
                job.hierarchy = hierarchy
                job.updated_at = _utcnow()
                db.commit()
            return
        with _memory_lock:
            mem = _memory_jobs.get(job_id)
            if mem:
                mem["hierarchy"] = hierarchy
                mem["updated_at"] = _utcnow().isoformat()

    def list_jobs(
        self,
        db: Session | None,
        *,
        limit: int = 50,
        user_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        if is_db_enabled() and db is not None:
            q = db.query(BudgetPriceMatchingJob).order_by(BudgetPriceMatchingJob.updated_at.desc())
            if user_id is not None:
                q = q.filter(BudgetPriceMatchingJob.user_id == user_id)
            jobs = q.limit(max(1, min(limit, 200))).all()
            return [j.to_dict() for j in jobs]

        with _memory_lock:
            items = sorted(
                _memory_jobs.values(),
                key=lambda j: str(j.get("updated_at") or ""),
                reverse=True,
            )
            return [{k: v for k, v in j.items() if k != "rows"} for j in items[:limit]]

    def link_budget(
        self,
        db: Session | None,
        job_id: str,
        *,
        budget_document_id: str | None,
        session_id: str | None,
        hierarchy: list[dict[str, Any]] | None = None,
    ) -> None:
        if is_db_enabled() and db is not None:
            jid = uuid.UUID(job_id)
            job = db.get(BudgetPriceMatchingJob, jid)
            if not job:
                return
            if budget_document_id:
                job.budget_document_id = uuid.UUID(budget_document_id)
            if session_id:
                job.session_id = session_id
            if hierarchy is not None:
                job.hierarchy = hierarchy
            job.status = "imported"
            job.updated_at = _utcnow()
            db.commit()
            return
        with _memory_lock:
            job = _memory_jobs.get(job_id)
            if not job:
                return
            if budget_document_id:
                job["budget_document_id"] = budget_document_id
            if session_id:
                job["session_id"] = session_id
            if hierarchy is not None:
                job["hierarchy"] = hierarchy
            job["status"] = "imported"

    def delete_job(self, db: Session | None, job_id: str) -> bool:
        if is_db_enabled() and db is not None:
            jid = uuid.UUID(job_id)
            job = db.get(BudgetPriceMatchingJob, jid)
            if not job:
                return False
            db.delete(job)
            db.commit()
            return True
        with _memory_lock:
            return _memory_jobs.pop(job_id, None) is not None


STORE = PriceMatchingStore()
