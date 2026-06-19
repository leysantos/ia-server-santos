#!/usr/bin/env python3
"""
Migração legado → knowledge/raw/documents/.

Consolida knowledge_base/ e layout {disciplina}/raw/ via resolver.migrate_legacy_layout_to_documents.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.settings import KNOWLEDGE_DIR
from core.knowledge.content_types import KNOWLEDGE_CONTENT_TYPES
from core.knowledge.resolver import (
    ensure_all_discipline_scaffold,
    migrate_legacy_layout_to_documents,
    prune_knowledge_orphans,
)

LEGACY_KB_DIR = BACKEND_DIR / "knowledge_base"


def migrate(*, execute: bool = False) -> dict:
    log: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": not execute,
        "legacy_dir": str(LEGACY_KB_DIR),
        "legacy_dir_exists": LEGACY_KB_DIR.exists(),
        "target": "knowledge/raw/documents/",
        "content_types": list(KNOWLEDGE_CONTENT_TYPES),
    }

    if execute:
        ensure_all_discipline_scaffold()
        moved = migrate_legacy_layout_to_documents(dry_run=False)
        pruned = prune_knowledge_orphans(dry_run=False)
        log["migrate"] = moved
        log["prune"] = pruned
        log["summary"] = {
            "moved": len(moved.get("moved", [])),
            "removed_dirs": len(pruned.get("removed_dirs", [])),
        }
    else:
        moved = migrate_legacy_layout_to_documents(dry_run=True)
        pruned = prune_knowledge_orphans(dry_run=True)
        log["migrate"] = moved
        log["prune"] = pruned
        log["summary"] = {
            "would_move": len(moved.get("moved", [])),
            "would_remove_dirs": len(pruned.get("removed_dirs", [])),
        }

    return log


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migra layout legado → knowledge/raw/documents/"
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--scaffold", action="store_true")
    args = parser.parse_args()

    if args.scaffold:
        paths = ensure_all_discipline_scaffold()
        print(json.dumps({"scaffold_dirs": len(paths)}, indent=2))
        return 0

    result = migrate(execute=args.execute)
    if args.execute:
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not args.execute:
        print("\n⚠️  Dry-run — use --execute para migrar e remover pastas legadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
