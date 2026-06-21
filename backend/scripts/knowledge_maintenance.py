#!/usr/bin/env python3
"""
Manutenção da base de conhecimento NBR.

  cd backend && ../.venv/bin/python scripts/knowledge_maintenance.py --all
  cd backend && ../.venv/bin/python scripts/knowledge_maintenance.py --purge-orphans
  cd backend && ../.venv/bin/python scripts/knowledge_maintenance.py --compact-faiss
  cd backend && ../.venv/bin/python scripts/knowledge_maintenance.py --index-pending
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import NBR_DIR
from core.knowledge.catalog_maintenance import (
    dedupe_catalog_by_path,
    purge_orphan_catalog_entries,
    repair_priority_norm_sidecars,
)
from core.knowledge.faiss_maintenance import maintain_all_faiss
from core.knowledge.pending_indexer import index_pending_nbr_pdfs, list_pending_nbr_pdfs


def main() -> int:
    parser = argparse.ArgumentParser(description="Manutenção knowledge NBR/FAISS")
    parser.add_argument("--all", action="store_true", help="Executa todas as etapas")
    parser.add_argument("--purge-orphans", action="store_true")
    parser.add_argument("--dedupe-catalog", action="store_true")
    parser.add_argument("--repair-norms", action="store_true")
    parser.add_argument("--compact-faiss", action="store_true")
    parser.add_argument("--index-pending", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-pending", action="store_true")
    args = parser.parse_args()

    if not any(
        [
            args.all,
            args.purge_orphans,
            args.dedupe_catalog,
            args.repair_norms,
            args.compact_faiss,
            args.index_pending,
            args.list_pending,
        ]
    ):
        parser.print_help()
        return 1

    results: dict = {}

    if args.list_pending or args.all:
        pending = list_pending_nbr_pdfs()
        results["pending_list"] = [p.name for p in pending]
        print(f"Pendentes: {len(pending)}")
        for p in pending[:20]:
            print(f"  - {p.name}")
        if len(pending) > 20:
            print(f"  … +{len(pending) - 20}")

    if args.purge_orphans or args.all:
        results["purge_orphans"] = purge_orphan_catalog_entries(dry_run=args.dry_run)
        print("purge_orphans:", json.dumps(results["purge_orphans"], ensure_ascii=False))

    if args.dedupe_catalog or args.all:
        results["dedupe_catalog"] = dedupe_catalog_by_path(dry_run=args.dry_run)
        print("dedupe_catalog:", json.dumps(results["dedupe_catalog"], ensure_ascii=False))

    if args.repair_norms or args.all:
        results["repair_norms"] = repair_priority_norm_sidecars(
            NBR_DIR, dry_run=args.dry_run
        )
        print("repair_norms:", json.dumps(results["repair_norms"], ensure_ascii=False))

    if args.compact_faiss or args.all:
        if args.dry_run:
            print("compact-faiss: ignorado em dry-run")
        else:
            results["compact_faiss"] = maintain_all_faiss(compact=True, reembed=False)
            print("compact_faiss:", json.dumps(results["compact_faiss"], ensure_ascii=False))

    if args.index_pending or args.all:
        if args.dry_run:
            print("index-pending: ignorado em dry-run")
        else:

            def _progress(data: dict) -> None:
                print(
                    f"\r  {data.get('percent', 0)}% {data.get('message', '')}",
                    end="",
                    flush=True,
                )

            results["index_pending"] = index_pending_nbr_pdfs(on_progress=_progress)
            print()
            cov = results["index_pending"].get("coverage") or {}
            print(
                "index_pending:",
                json.dumps(
                    {
                        k: results["index_pending"].get(k)
                        for k in (
                            "pending_files",
                            "indexed_files",
                            "indexed_chunks",
                            "ocr_files",
                            "empty_files",
                            "errors",
                        )
                    },
                    ensure_ascii=False,
                ),
            )
            print(f"coverage: {cov.get('coverage_pct')}% codes={cov.get('code_coverage_pct')}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
