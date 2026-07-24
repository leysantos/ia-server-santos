"""Persistência e leitura de CPUs abertas — cache global deduplicado (code + reference + uf)."""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database.models import CompositionOpenCache
from pricing.budget.budget_export_tables import collect_export_composition_lookups
from pricing.budget.composition_lookup import resolve_composition_detail
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata

logger = logging.getLogger(__name__)


def composition_fetch_key(code: str, reference: str, uf: str) -> str:
    return f"{code.strip()}|{reference.strip()}|{uf.strip().upper()}"


def _serialize_detail(detail: dict[str, Any]) -> dict[str, Any]:
    out = dict(detail)
    out.pop("reference_fallback", None)
    return out


def _resolve_one(code: str, reference: str, uf: str) -> dict[str, Any] | None:
    try:
        comp = resolve_composition_detail(code, uf=uf.upper(), reference=reference)
        return _serialize_detail(comp) if comp else None
    except Exception:
        logger.debug("composition resolve failed for %s @ %s/%s", code, reference, uf, exc_info=True)
        return None


def _cache_values(
    code: str,
    reference: str,
    uf: str,
    detail: dict[str, Any],
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    now = captured_at or datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "composition_code": code.strip(),
        "reference": reference.strip(),
        "uf": uf.strip().upper(),
        "detail_json": _serialize_detail(detail),
        "hit_count": 0,
        "captured_at": now,
        "updated_at": now,
    }


def load_cache_map(
    db: Session,
    keys: Iterable[tuple[str, str, str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Carrega entradas do cache global; opcionalmente filtra por (code, ref, uf)."""
    query = db.query(CompositionOpenCache)
    if keys is not None:
        key_set = {
            (code.strip(), reference.strip(), uf.strip().upper())
            for code, reference, uf in keys
        }
        if not key_set:
            return {}
        codes = {k[0] for k in key_set}
        refs = {k[1] for k in key_set}
        ufs = {k[2] for k in key_set}
        rows = (
            query.filter(
                CompositionOpenCache.composition_code.in_(codes),
                CompositionOpenCache.reference.in_(refs),
                CompositionOpenCache.uf.in_(ufs),
            ).all()
        )
        return {
            composition_fetch_key(r.composition_code, r.reference, r.uf): dict(r.detail_json or {})
            for r in rows
            if (r.composition_code, r.reference, r.uf) in key_set
        }

    rows = query.all()
    return {
        composition_fetch_key(r.composition_code, r.reference, r.uf): dict(r.detail_json or {})
        for r in rows
    }


def upsert_cache_entry(
    db: Session,
    code: str,
    reference: str,
    uf: str,
    detail: dict[str, Any],
) -> None:
    """Upsert atômico no cache global — seguro para concorrência."""
    values = _cache_values(code, reference, uf, detail)
    bind = db.get_bind()
    dialect = bind.dialect.name if bind is not None else ""

    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(CompositionOpenCache).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_comp_open_cache_code_ref_uf",
            set_={
                "detail_json": stmt.excluded.detail_json,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db.execute(stmt)
        return

    existing = (
        db.query(CompositionOpenCache)
        .filter(
            CompositionOpenCache.composition_code == values["composition_code"],
            CompositionOpenCache.reference == values["reference"],
            CompositionOpenCache.uf == values["uf"],
        )
        .one_or_none()
    )
    if existing:
        existing.detail_json = values["detail_json"]
        existing.updated_at = values["updated_at"]
    else:
        db.add(CompositionOpenCache(**values))
    db.flush()


def _commit_cache(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("composition cache commit conflict — rolled back", exc_info=True)


def _bump_cache_hits(db: Session, keys: list[tuple[str, str, str]]) -> None:
    if not keys:
        return
    codes = {k[0] for k in keys}
    refs = {k[1] for k in keys}
    ufs = {k[2] for k in keys}
    rows = (
        db.query(CompositionOpenCache)
        .filter(
            CompositionOpenCache.composition_code.in_(codes),
            CompositionOpenCache.reference.in_(refs),
            CompositionOpenCache.uf.in_(ufs),
        )
        .all()
    )
    key_set = set(keys)
    for row in rows:
        triple = (row.composition_code, row.reference, row.uf)
        if triple in key_set:
            row.hit_count = (row.hit_count or 0) + 1


def sync_missing_snapshots(
    db: Session,
    budget_document_id: uuid.UUID | None,
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    *,
    max_workers: int = 8,
) -> dict[str, int]:
    """Grava no cache global apenas CPUs ainda ausentes."""
    del budget_document_id  # legado — cache é global
    required = collect_export_composition_lookups(roots, meta)
    if not required:
        return {"required": 0, "stored": 0, "fetched": 0}

    stored = load_cache_map(db, required)
    missing: list[tuple[str, str, str]] = []
    for code, ref, uf in required:
        key = composition_fetch_key(code, ref, uf)
        if key not in stored:
            missing.append((code, ref, uf))

    if not missing:
        return {"required": len(required), "stored": len(stored), "fetched": 0}

    fetched = 0

    def _load(key: tuple[str, str, str]) -> tuple[tuple[str, str, str], dict[str, Any] | None]:
        code, ref, uf = key
        return key, _resolve_one(code, ref, uf)

    workers = min(max_workers, len(missing))
    if workers <= 1:
        results = [_load(key) for key in missing]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_load, key) for key in missing]
            for fut in as_completed(futures):
                results.append(fut.result())

    for (code, ref, uf), detail in results:
        if not detail:
            continue
        upsert_cache_entry(db, code, ref, uf, detail)
        fetched += 1

    if fetched:
        _commit_cache(db)

    return {"required": len(required), "stored": len(stored) + fetched, "fetched": fetched}


def sync_all_snapshots(
    db: Session,
    budget_document_id: uuid.UUID | None,
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    *,
    max_workers: int = 8,
) -> dict[str, int]:
    """Força refresh de todas as CPUs do orçamento no cache global."""
    del budget_document_id
    required = collect_export_composition_lookups(roots, meta)
    if not required:
        return {"required": 0, "fetched": 0}

    fetched = 0

    def _load(key: tuple[str, str, str]) -> tuple[tuple[str, str, str], dict[str, Any] | None]:
        code, ref, uf = key
        return key, _resolve_one(code, ref, uf)

    workers = min(max_workers, len(required))
    if workers <= 1:
        results = [_load(key) for key in required]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_load, key) for key in required]
            for fut in as_completed(futures):
                results.append(fut.result())

    for (code, ref, uf), detail in results:
        if not detail:
            continue
        upsert_cache_entry(db, code, ref, uf, detail)
        fetched += 1

    if fetched:
        _commit_cache(db)

    return {"required": len(required), "fetched": fetched}


def schedule_snapshot_sync(
    budget_document_id: uuid.UUID | str,
    payload: dict[str, Any],
    *,
    force_all: bool = False,
) -> None:
    """Persiste cache em thread separada — não bloqueia HTTP."""
    import threading

    doc_id = str(budget_document_id)
    payload_copy = dict(payload)

    def _run() -> None:
        from core.database.connection import SessionLocal

        db = SessionLocal()
        try:
            sync_snapshots_from_payload(
                db, doc_id, payload_copy, force_all=force_all
            )
        except Exception:
            logger.warning("background composition cache sync failed", exc_info=True)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True, name=f"cache-sync-{doc_id[:8]}").start()


def sync_snapshots_from_payload(
    db: Session,
    budget_document_id: uuid.UUID | str,
    payload: dict[str, Any],
    *,
    force_all: bool = False,
) -> dict[str, int]:
    from app.services.budget_db_service import session_from_payload

    session = session_from_payload(payload)
    if force_all:
        return sync_all_snapshots(db, None, session.roots, session.project)
    return sync_missing_snapshots(db, None, session.roots, session.project)


def get_batch_compositions(
    db: Session | None,
    *,
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    budget_document_id: uuid.UUID | str | None = None,
    backfill: bool = False,
    max_workers: int = 8,
) -> dict[str, Any]:
    """
    Retorna mapa fetch_key → OpenCompositionDetail.
    Lê cache global; opcionalmente backfill das ausentes.
    """
    del budget_document_id  # legado — leitura não depende mais do orçamento
    required = collect_export_composition_lookups(roots, meta)
    snapshots: dict[str, dict[str, Any]] = {}
    from_cache = 0
    from_bank = 0

    stored: dict[str, dict[str, Any]] = {}
    cache_hits: list[tuple[str, str, str]] = []
    if db is not None and required:
        stored = load_cache_map(db, required)

    missing: list[tuple[str, str, str]] = []
    for code, ref, uf in required:
        key = composition_fetch_key(code, ref, uf)
        if key in stored:
            snapshots[key] = stored[key]
            from_cache += 1
            cache_hits.append((code.strip(), ref.strip(), uf.strip().upper()))
        else:
            missing.append((code, ref, uf))

    if cache_hits and db is not None:
        try:
            _bump_cache_hits(db, cache_hits)
            db.commit()
        except Exception:
            db.rollback()

    if missing:
        resolved: list[tuple[tuple[str, str, str], dict[str, Any] | None]] = []

        def _load(key: tuple[str, str, str]) -> tuple[tuple[str, str, str], dict[str, Any] | None]:
            code, ref, uf = key
            return key, _resolve_one(code, ref, uf)

        workers = min(max_workers, len(missing))
        if workers <= 1:
            for key in missing:
                try:
                    resolved.append(_load(key))
                except Exception:
                    logger.warning("batch composition load failed for %s", key, exc_info=True)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_load, key) for key in missing]
                for fut in as_completed(futures):
                    try:
                        resolved.append(fut.result())
                    except Exception:
                        logger.warning("batch composition worker failed", exc_info=True)

        for (code, ref, uf), detail in resolved:
            if not detail:
                continue
            key = composition_fetch_key(code, ref, uf)
            snapshots[key] = detail
            from_bank += 1
            if backfill and db is not None:
                upsert_cache_entry(db, code, ref, uf, detail)

        if backfill and db is not None and from_bank:
            _commit_cache(db)

    missing_keys = [
        composition_fetch_key(code, ref, uf)
        for code, ref, uf in required
        if composition_fetch_key(code, ref, uf) not in snapshots
    ]

    return {
        "snapshots": snapshots,
        "total": len(required),
        "from_cache": from_cache,
        "from_db": from_cache,
        "from_bank": from_bank,
        "missing": missing_keys,
    }


def preload_export_cache(
    db: Session,
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
) -> int:
    """Preenche _EXPORT_COMPOSITION_CACHE a partir do cache global."""
    from pricing.budget.budget_export_tables import _EXPORT_COMPOSITION_CACHE

    required = collect_export_composition_lookups(roots, meta)
    if not required:
        return 0

    stored = load_cache_map(db, required)
    count = 0
    for code, ref, uf in required:
        key = composition_fetch_key(code, ref, uf)
        detail = stored.get(key)
        if not detail:
            continue
        items = list(detail.get("items") or [])
        cache_key = (code.strip(), ref.strip(), uf.strip().upper())
        _EXPORT_COMPOSITION_CACHE[cache_key] = items
        count += 1
    return count


def preload_export_cache_from_db(db: Session, budget_document_id: uuid.UUID) -> int:
    """Legado — use preload_export_cache com roots/meta."""
    del budget_document_id
    return 0


def upsert_snapshot_for_service(
    db: Session,
    budget_document_id: uuid.UUID | str | None,
    *,
    code: str,
    reference: str,
    uf: str,
) -> bool:
    del budget_document_id
    detail = _resolve_one(code, reference, uf)
    if not detail:
        return False
    upsert_cache_entry(db, code, reference, uf, detail)
    _commit_cache(db)
    return True
