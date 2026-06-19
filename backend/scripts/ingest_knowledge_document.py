#!/usr/bin/env python3
"""
Ingestão disciplinar — Knowledge Activation Layer.

Pipeline: arquivo → classifier → knowledge/raw/documents/ + .knowledge.json

Uso:
  cd backend
  python3 scripts/ingest_knowledge_document.py --file /path/NBR-6118.pdf
  python3 scripts/ingest_knowledge_document.py --file doc.pdf --discipline ESTRUTURAL
  python3 scripts/ingest_knowledge_document.py --dir /path/to/pdfs/ --dry-run

Destino: backend/knowledge/raw/documents/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from core.knowledge.ingestion import get_ingester

_SUFFIXES = {".pdf", ".csv", ".xlsx", ".xls", ".json", ".md", ".txt"}


def _collect_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in _SUFFIXES
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingestão disciplinar de documentos")
    parser.add_argument("--file", type=Path, help="Arquivo único")
    parser.add_argument("--dir", type=Path, help="Diretório (ingere recursivamente)")
    parser.add_argument("--content-type", type=str, help="Tipo: nbrs, sinapi, tcpo, tdrs, ...")
    parser.add_argument("--discipline", type=str, help="Disciplina forçada (ex.: ESTRUTURAL)")
    parser.add_argument("--layer", type=str, default="raw", help="Layer destino (default: raw)")
    parser.add_argument("--force", action="store_true", help="Sobrescrever se existir")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só classificar, não copiar",
    )
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("Informe --file ou --dir")

    print(json.dumps({
        "USE_DISCIPLINE_INGESTION": settings.USE_DISCIPLINE_INGESTION,
        "KNOWLEDGE_DIR": str(settings.KNOWLEDGE_DIR),
    }, indent=2))

    sources: list[Path] = []
    if args.file:
        sources.extend(_collect_files(args.file))
    if args.dir:
        sources.extend(_collect_files(args.dir))

    ingester = get_ingester()
    summary = ingester.ingest_batch(
        sources,
        discipline_hint=args.discipline,
        content_type_hint=args.content_type,
        layer=args.layer,
        copy=not args.dry_run,
        force=args.force,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not summary.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
