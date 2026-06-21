#!/usr/bin/env python3
"""
Indexa bases de conhecimento técnicas em índices FAISS separados.

Fonte canônica: backend/knowledge/ (via core/knowledge/resolver.py)

Uso:
  cd backend
  python scripts/index_knowledge_bases.py              # todas as bases
  python scripts/index_knowledge_bases.py --base nbr   # só NBR
  python scripts/index_knowledge_bases.py --force      # reindexar
  python scripts/index_knowledge_bases.py --stats      # estatísticas

IMPORTANTE: Evolution Loop e Agent Generation NUNCA executam este script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from core.knowledge.constants import IMMUTABLE_KNOWLEDGE_BASES, KNOWLEDGE_PATHS
    from core.knowledge.knowledge_indexer import KnowledgeIndexer
except ModuleNotFoundError as exc:
    if "pydantic_settings" in str(exc):
        print(
            "ERRO: dependências do backend não encontradas.\n"
            "Use o venv do projeto:\n"
            "  cd backend && ../.venv/bin/python scripts/index_knowledge_bases.py\n"
            "Ou na raiz: make index-knowledge",
            file=sys.stderr,
        )
        sys.exit(1)
    raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Indexa bases de conhecimento multi-FAISS")
    parser.add_argument(
        "--base",
        choices=list(KNOWLEDGE_PATHS.keys()),
        help="Indexar apenas uma base (default: todas)",
    )
    parser.add_argument("--force", action="store_true", help="Reindexar arquivos já indexados")
    parser.add_argument("--stats", action="store_true", help="Mostrar estatísticas dos índices")
    args = parser.parse_args()

    if not IMMUTABLE_KNOWLEDGE_BASES:
        print("AVISO: IMMUTABLE_KNOWLEDGE_BASES=false — modo dev")

    indexer = KnowledgeIndexer()

    if args.stats:
        from core.knowledge.knowledge_base_router import get_knowledge_router

        print(json.dumps(get_knowledge_router().stats(), indent=2, ensure_ascii=False))
        return 0

    if args.base:
        summary = indexer.index_base(args.base, force=args.force)
    else:
        summary = indexer.index_all(force=args.force)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not summary.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
