#!/usr/bin/env python3
"""Benchmark do cache global de CPUs abertas (composition_open_cache).

Uso:
  cd backend && python scripts/bench_composition_cache.py
  cd backend && python scripts/bench_composition_cache.py --limit 3 --backfill
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark composition_open_cache")
    p.add_argument("--limit", type=int, default=2, help="Orçamentos a testar (mais recentes)")
    p.add_argument("--backfill", action="store_true", help="Grava misses no cache global")
    p.add_argument("--rounds", type=int, default=3, help="Repetições por cenário")
    return p.parse_args()


def _load_budgets(db, limit: int):
    from core.database.models import BudgetDocument

    rows = (
        db.query(BudgetDocument)
        .order_by(BudgetDocument.updated_at.desc())
        .limit(limit)
        .all()
    )
    return rows


def _session_from_doc(doc):
    from app.services.budget_db_service import session_from_payload

    return session_from_payload(doc.payload or {})


def _bench_once(fn) -> tuple[float, dict]:
    t0 = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - t0
    return elapsed, result


def _fmt_stats(times: list[float]) -> str:
    if not times:
        return "n/a"
    if len(times) == 1:
        return f"{times[0]*1000:.1f} ms"
    return (
        f"med={statistics.median(times)*1000:.1f} ms "
        f"p95={sorted(times)[int(len(times)*0.95)-1]*1000:.1f} ms "
        f"min={min(times)*1000:.1f} ms max={max(times)*1000:.1f} ms"
    )


def main() -> int:
    args = _parse_args()

    from core.database.connection import SessionLocal, init_db
    from pricing.budget.composition_snapshot_service import get_batch_compositions

    init_db()
    db = SessionLocal()

    try:
        docs = _load_budgets(db, args.limit)
        if not docs:
            print("Nenhum orçamento no banco — salve um orçamento antes do benchmark.")
            return 1

        from core.database.models import CompositionOpenCache

        cache_rows = db.query(CompositionOpenCache).count()
        print(f"Cache global: {cache_rows} entradas")
        print(f"Orçamentos: {len(docs)}")
        print("-" * 60)

        for i, doc in enumerate(docs, 1):
            session = _session_from_doc(doc)
            title = (doc.title or "")[:50]
            print(f"\n[{i}] {title} ({doc.id})")

            def _run():
                return get_batch_compositions(
                    db,
                    roots=session.roots,
                    meta=session.project,
                    backfill=args.backfill,
                )

            cold_times: list[float] = []
            warm_times: list[float] = []
            last: dict = {}

            for r in range(args.rounds):
                db.rollback()
                elapsed, result = _bench_once(_run)
                last = result
                label = "cold" if r == 0 else "warm"
                if r == 0:
                    cold_times.append(elapsed)
                else:
                    warm_times.append(elapsed)
                print(
                    f"  round {r+1} ({label}): {elapsed*1000:.1f} ms — "
                    f"total={result['total']} cache={result['from_cache']} "
                    f"bank={result['from_bank']} missing={len(result['missing'])}"
                )

            print(f"  cold: {_fmt_stats(cold_times)}")
            print(f"  warm: {_fmt_stats(warm_times)}")

        if len(docs) >= 2:
            print("\n" + "=" * 60)
            print("Reuso cross-orçamento (2º orçamento após warm do 1º)")
            doc_a, doc_b = docs[0], docs[1]
            sess_a = _session_from_doc(doc_a)
            sess_b = _session_from_doc(doc_b)

            get_batch_compositions(
                db, roots=sess_a.roots, meta=sess_a.project, backfill=True
            )
            db.commit()

            cross_times: list[float] = []
            cross_result: dict = {}
            for _ in range(args.rounds):
                db.rollback()
                elapsed, cross_result = _bench_once(
                    lambda: get_batch_compositions(
                        db, roots=sess_b.roots, meta=sess_b.project, backfill=False
                    )
                )
                cross_times.append(elapsed)

            print(
                f"  total={cross_result.get('total')} cache={cross_result.get('from_cache')} "
                f"bank={cross_result.get('from_bank')} missing={len(cross_result.get('missing', []))}"
            )
            print(f"  latência: {_fmt_stats(cross_times)}")

        cache_rows_after = db.query(CompositionOpenCache).count()
        print(f"\nCache global após benchmark: {cache_rows_after} entradas (+{cache_rows_after - cache_rows})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
