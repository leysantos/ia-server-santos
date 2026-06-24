#!/usr/bin/env python3
"""
Sincroniza bases de preço oficiais (SINAPI Caixa, ORSE, TCPO, CICRO).

  cd backend && ../.venv/bin/python scripts/sync_price_bases.py --source sinapi --uf SP
  cd backend && ../.venv/bin/python scripts/sync_price_bases.py --all
  cd backend && ../.venv/bin/python scripts/sync_price_bases.py --source orse --file /path/export.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.sync.service import get_price_sync_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync bases de preço SINAPI/ORSE/TCPO")
    parser.add_argument("--source", choices=["sinapi", "orse", "tcpo", "cicro"])
    parser.add_argument("--all", action="store_true", help="Sincroniza fontes com download automático")
    parser.add_argument("--all-ufs", action="store_true", help="SICRO: baixa todas as UFs do portal DNIT")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="SICRO (--all-ufs): pular UFs já importadas no mesmo ano/mês",
    )
    parser.add_argument("--uf", default="SP", help="UF SINAPI (default SP)")
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    parser.add_argument("--desonerado", action="store_true", default=True)
    parser.add_argument("--nao-desonerado", action="store_true")
    parser.add_argument("--file", type=Path, help="Arquivo local (ORSE/TCPO/CICRO ou SINAPI manual)")
    parser.add_argument("--status", action="store_true", help="Mostra estado das syncs")
    parser.add_argument("--no-faiss", action="store_true")
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    service = get_price_sync_service()

    if args.status:
        print(json.dumps(service.status(), indent=2, ensure_ascii=False))
        return 0

    if not args.source and not args.all:
        parser.print_help()
        return 1

    options: dict = {}
    if args.file:
        options["local_file"] = args.file
    if args.source == "sinapi" or args.all:
        options.update(
            {
                "uf": args.uf,
                "year": args.year,
                "month": args.month,
                "desonerado": not args.nao_desonerado,
            }
        )
    if args.source == "cicro" or (args.all and args.source is None):
        options.update(
            {
                "uf": args.uf,
                "year": args.year,
                "month": args.month,
                "desonerado": not args.nao_desonerado,
                "download_all_regions": args.all_ufs,
                "skip_existing_ufs": args.skip_existing,
            }
        )

    common = {
        "index_faiss": not args.no_faiss,
        "reload_providers": not args.no_reload,
    }

    if args.all:
        result = service.sync_all(**common, **options)
    else:
        result = service.sync(args.source, **common, **options)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    errors = result.get("errors") if isinstance(result, dict) else None
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
