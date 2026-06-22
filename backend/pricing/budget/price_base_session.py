"""Aplica seleção de bases de preço (UF + período) ao provider SINAPI da sessão."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REF_PATTERN = re.compile(r"^BR-(\d{4})-(\d{2})$", re.I)


def reference_label(reference: str) -> str:
    m = REF_PATTERN.match(reference.replace("/", "-"))
    if m:
        return f"{m.group(2)}/{m.group(1)}"
    return reference


def apply_price_bases_selection(selections: list[dict[str, Any]]) -> dict[str, Any]:
    """Carrega composições fechadas da referência/UF escolhidas no provider global."""
    enabled = [s for s in selections if s.get("enabled")]
    if not enabled:
        raise ValueError("Selecione ao menos uma base de preços")

    primary = enabled[0]
    source = str(primary.get("source") or "sinapi").lower()
    uf = str(primary.get("uf") or "SP").upper()
    reference = str(primary.get("reference") or "").replace("/", "-")
    if not reference:
        raise ValueError("Período da base SINAPI não informado")

    from pricing.budget.price_bank_store import PriceBankStore

    rows = PriceBankStore.for_reference(reference).closed_as_provider_rows(uf=uf)
    if not rows:
        raise ValueError(f"Nenhuma composição em {reference} para UF {uf}")

    summary = _load_provider_rows(source, rows, reference=reference, uf=uf)

    labels: list[str] = []
    for sel in enabled:
        lbl = str(sel.get("label") or sel.get("source") or "").upper()
        ref = reference_label(str(sel.get("reference") or ""))
        labels.append(f"{lbl} {sel.get('uf', 'SP')} {ref}".strip())

    return {
        **summary,
        "base_preco": " · ".join(labels),
        "source_priority": [str(s.get("source") or "sinapi").lower() for s in enabled],
        "primary": {"source": source, "uf": uf, "reference": reference},
    }


def _load_provider_rows(
    provider_name: str,
    rows: list[dict[str, Any]],
    *,
    reference: str,
    uf: str,
) -> dict[str, Any]:
    from pricing.bootstrap import ensure_providers_registered
    from pricing.models.price_source import PriceSource
    from pricing.registry.provider_registry import ProviderRegistry

    ensure_providers_registered()
    provider = ProviderRegistry.get(provider_name)
    if not provider:
        raise ValueError(f"Provider '{provider_name}' não registrado")

    stem = f"{provider_name}_{reference}_{uf}".replace("/", "-")
    from config.settings import KNOWLEDGE_DIR

    dest_dir = KNOWLEDGE_DIR / "sync" / "price_bases" / provider_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{stem}_fechadas.csv"

    from pricing.sync.sinapi_parser import export_sinapi_csv

    export_sinapi_csv(rows, dest)

    provider._data = rows  # noqa: SLF001
    provider._source = PriceSource(  # noqa: SLF001
        name=provider_name,
        label=f"{provider.label} {uf} {reference_label(reference)}",
        item_count=len(rows),
        path=str(dest),
    )

    if provider_name == "sinapi" and rows:
        try:
            from pricing.budget.composition_index import get_composition_index

            index = get_composition_index()
            if len(rows) > 800:
                index.schedule_rebuild(rows, label=stem, source="sinapi")
            else:
                index.rebuild(rows, label=stem, source="sinapi")
        except Exception as exc:
            logger.warning("FAISS composições após aplicar base: %s", exc)

    return {
        "provider": provider_name,
        "item_count": len(rows),
        "path": str(dest),
        "reference": reference,
        "uf": uf,
    }
