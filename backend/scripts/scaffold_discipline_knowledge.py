#!/usr/bin/env python3
"""
Scaffold knowledge/raw/documents/ — única pasta de storage.

  python3 scripts/scaffold_discipline_knowledge.py
  python3 scripts/scaffold_discipline_knowledge.py --prune --migrate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from core.knowledge.resolver import (
    ensure_all_discipline_scaffold,
    get_documents_dir,
    migrate_legacy_layout_to_documents,
    prune_knowledge_orphans,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold knowledge/raw/documents/")
    parser.add_argument("--prune", action="store_true", help="Remove layout legado")
    parser.add_argument("--migrate", action="store_true", help="Consolidar arquivos antigos")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.migrate or args.prune:
        if args.migrate and not args.prune:
            print(json.dumps(
                migrate_legacy_layout_to_documents(dry_run=args.dry_run),
                indent=2,
            ))
        if args.prune:
            print(json.dumps(prune_knowledge_orphans(dry_run=args.dry_run), indent=2))

    created = ensure_all_discipline_scaffold()
    print(
        json.dumps(
            {
                "documents_dir": str(get_documents_dir()),
                "dirs": len(created),
                "pattern": "knowledge/raw/documents/{filename}",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
