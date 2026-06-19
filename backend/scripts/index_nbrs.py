#!/usr/bin/env python3
"""
Indexação de PDFs NBR para o RAG do IA Server Santos.

Uso:
    python scripts/index_nbrs.py                  # indexa knowledge/raw/documents/
    python scripts/index_nbrs.py --file NBR-6118.pdf
    python scripts/index_nbrs.py --discipline ESTRUTURAL
    python scripts/index_nbrs.py --force          # reindexa PDFs já indexados
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import NBR_DIR
from memory.rag_engine import RAGEngine


def main():
    parser = argparse.ArgumentParser(description="Indexa PDFs NBR no RAG")
    parser.add_argument(
        "--file",
        type=str,
        help="Caminho de um PDF específico (padrão: todos em knowledge/raw/documents/)",
    )
    parser.add_argument(
        "--discipline",
        type=str,
        default="",
        help="Disciplina forçada (ex.: ESTRUTURAL). Se omitida, infere pelo nome NBR.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reindexa PDFs já presentes no índice",
    )
    args = parser.parse_args()

    engine = RAGEngine()

    if args.file:
        pdf_path = Path(args.file)
        if not pdf_path.is_absolute():
            candidate = NBR_DIR / pdf_path
            pdf_path = candidate if candidate.exists() else Path(args.file)

        count = engine.index_pdf(
            pdf_path=pdf_path,
            doc_type="nbr",
            discipline=args.discipline,
            force=args.force,
        )
        summary = {
            "indexed_files": 1 if count else 0,
            "skipped_files": 0 if count else 1,
            "indexed_chunks": count,
            "errors": [],
            "files": [{"file": pdf_path.name, "status": "indexed" if count else "skipped", "chunks": count}],
        }
    else:
        summary = engine.index_nbrs(discipline=args.discipline, force=args.force)

    summary["total_chunks_in_store"] = engine.indexed_chunks
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
