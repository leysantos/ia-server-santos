#!/usr/bin/env python3
"""Repara nomes «NBR 6118» → «NBR 6118 - Título…» no catálogo existente."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.knowledge_service import _dedupe_catalog_rows  # noqa: E402
from core.knowledge.catalog import read_catalog  # noqa: E402
from core.knowledge.norm_bulk.repair_titles import repair_bare_norm_catalog_names  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Somente listar alterações, sem gravar",
    )
    args = parser.parse_args()

    rows = _dedupe_catalog_rows(read_catalog())
    result = repair_bare_norm_catalog_names(rows, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
