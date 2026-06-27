#!/usr/bin/env python3
"""
Indexa bases de preço operacionais (SINAPI/SICRO/SEMINF) a partir do price_bank.

Arquitetura atual (Jun/26):
  - Orçamento: knowledge/price_bank/ + FAISS em memory/faiss_index/budget/compositions/
  - NÃO usa knowledge/cost_index (legado RAG) — ver docs/project_state.md

Uso:
  cd backend
  ../.venv/bin/python scripts/index_price_bases.py              # referência ativa
  ../.venv/bin/python scripts/index_price_bases.py --stats      # só status
  ../.venv/bin/python scripts/index_price_bases.py --force      # rebuild FAISS síncrono
  ../.venv/bin/python scripts/index_price_bases.py --reference BR-2026-05 --uf AM
  ../.venv/bin/python scripts/index_price_bases.py --load-tabular  # TCPO/ORSE em pricing/data/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _default_uf(reference: str) -> str:
    from pricing.budget.price_bank_index import PriceBankIndex

    for entry in PriceBankIndex.load().references:
        if entry.reference == reference:
            return (entry.default_uf or "SP").upper()
    return "SP"


def _resolve_reference(explicit: str | None) -> str:
    from pricing.budget.price_bank_index import PriceBankIndex

    idx = PriceBankIndex.load()
    if explicit:
        return explicit.replace("/", "-").upper()
    if idx.active_reference:
        return idx.active_reference
    sinapi = next((r for r in idx.references if r.source == "sinapi"), None)
    if sinapi:
        return sinapi.reference
    if idx.references:
        return idx.references[0].reference
    raise SystemExit("Nenhuma referência no price_bank — importe SINAPI em /settings/price-bases")


def _composition_status() -> dict:
    from pricing.budget.composition_index import get_composition_index

    return get_composition_index().status()


def _load_tabular_providers() -> dict[str, int]:
    from pricing.bootstrap import load_default_bases

    return load_default_bases()


def index_active_price_base(
    *,
    reference: str,
    uf: str,
    source: str = "sinapi",
    force: bool = False,
) -> dict:
    from pricing.budget.price_bank_store import PriceBankStore
    from pricing.budget.price_base_session import apply_price_bases_selection
    from pricing.budget.composition_index import get_composition_index

    rows = PriceBankStore.for_reference(reference).closed_as_provider_rows(uf=uf)
    if not rows:
        raise SystemExit(f"Sem composições fechadas em {reference} (UF {uf})")

    applied = apply_price_bases_selection(
        [
            {
                "enabled": True,
                "source": source,
                "uf": uf,
                "reference": reference,
                "label": source.upper(),
            }
        ]
    )

    faiss: dict = {"skipped": True, "indexed": _composition_status().get("indexed", 0)}
    if force or not get_composition_index().is_current(rows, f"{source}_{reference}_{uf}"):
        label = f"{source}_{reference}_{uf}".replace("/", "-")
        faiss = get_composition_index().rebuild(rows, label=label, source=source)

    return {
        "reference": reference,
        "uf": uf,
        "source": source,
        "compositions": len(rows),
        "provider": applied,
        "faiss": faiss,
        "composition_index": _composition_status(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Indexa price_bank → providers + composition FAISS")
    parser.add_argument("--reference", help="Referência BR-YYYY-MM (default: ativa no index.json)")
    parser.add_argument("--uf", help="UF regional (default: default_uf da referência)")
    parser.add_argument("--source", default="sinapi", help="Provider alvo (sinapi, cicro, dp_seminf)")
    parser.add_argument("--force", action="store_true", help="Rebuild FAISS síncrono (ignora cache)")
    parser.add_argument("--stats", action="store_true", help="Mostrar status sem reindexar")
    parser.add_argument(
        "--load-tabular",
        action="store_true",
        help="Carregar TCPO/ORSE/CSV legado de pricing/data/ (sem FAISS budget)",
    )
    args = parser.parse_args()

    if args.stats:
        from pricing.budget.price_bank_index import PriceBankIndex

        payload = {
            "price_bank": {
                "active_reference": PriceBankIndex.load().active_reference,
                "references": len(PriceBankIndex.load().references),
            },
            "composition_index": _composition_status(),
        }
        if args.load_tabular:
            payload["tabular_providers"] = _load_tabular_providers()
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    reference = _resolve_reference(args.reference)
    uf = (args.uf or _default_uf(reference)).upper()

    summary = index_active_price_base(
        reference=reference,
        uf=uf,
        source=args.source.lower(),
        force=args.force,
    )

    if args.load_tabular:
        summary["tabular_providers"] = _load_tabular_providers()

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    errors = summary.get("faiss", {}).get("errors") or []
    indexed = int(summary.get("faiss", {}).get("indexed") or summary.get("composition_index", {}).get("indexed") or 0)
    if indexed <= 0 and not errors:
        return 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
