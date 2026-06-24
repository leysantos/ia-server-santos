"""Aplica seleção de bases de preço (UF + período) ao provider SINAPI da sessão."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REF_PATTERN = re.compile(r"^BR-(\d{4})-(\d{2})$", re.I)

_LOADED_FINGERPRINT: str | None = None
_LOADED_RESULT: dict[str, Any] | None = None


def _selection_fingerprint(selections: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for sel in sorted(selections, key=lambda s: str(s.get("source") or "")):
        if not sel.get("enabled"):
            continue
        parts.append(
            "|".join(
                [
                    str(sel.get("source") or "sinapi").lower(),
                    str(sel.get("uf") or "SP").upper(),
                    str(sel.get("reference") or "").replace("/", "-"),
                ]
            )
        )
    return "::".join(parts)


def _providers_match_fingerprint(fingerprint: str) -> bool:
    from pricing.bootstrap import ensure_providers_registered
    from pricing.registry.provider_registry import ProviderRegistry

    ensure_providers_registered()
    if not fingerprint:
        return False
    for chunk in fingerprint.split("::"):
        source, _uf, _reference = chunk.split("|", 2)
        provider = ProviderRegistry.get(source)
        if not provider or not provider.is_loaded:
            return False
        if not getattr(provider, "_data", []):
            return False
    return True


def reference_label(reference: str) -> str:
    m = REF_PATTERN.match(reference.replace("/", "-"))
    if m:
        return f"{m.group(2)}/{m.group(1)}"
    return reference


def apply_price_bases_selection(selections: list[dict[str, Any]]) -> dict[str, Any]:
    """Carrega composições fechadas de cada base habilitada no provider correspondente."""
    global _LOADED_FINGERPRINT, _LOADED_RESULT

    enabled = [s for s in selections if s.get("enabled")]
    if not enabled:
        raise ValueError("Selecione ao menos uma base de preços")

    fingerprint = _selection_fingerprint(enabled)
    if (
        fingerprint
        and fingerprint == _LOADED_FINGERPRINT
        and _LOADED_RESULT
        and _providers_match_fingerprint(fingerprint)
    ):
        return dict(_LOADED_RESULT)

    from pricing.budget.price_bank_store import PriceBankStore

    summaries: list[dict[str, Any]] = []
    labels: list[str] = []
    source_priority: list[str] = []

    for sel in enabled:
        source = str(sel.get("source") or "sinapi").lower()
        uf = str(sel.get("uf") or "SP").upper()
        reference = str(sel.get("reference") or "").replace("/", "-")
        if not reference:
            raise ValueError(f"Período da base {source.upper()} não informado")

        rows = PriceBankStore.for_reference(reference).closed_as_provider_rows(uf=uf)
        if not rows:
            raise ValueError(f"Nenhuma composição em {reference} para UF {uf}")

        summary = _load_provider_rows(source, rows, reference=reference, uf=uf)
        summaries.append(summary)
        source_priority.append(source)

        lbl = str(sel.get("label") or sel.get("source") or "").upper()
        ref_key = str(sel.get("reference") or "").replace("/", "-")
        ref = reference_label(ref_key) if REF_PATTERN.match(ref_key) else ref_key
        labels.append(f"{lbl} {uf} {ref}".strip())

    primary_sel = enabled[0]
    primary_summary = summaries[0]
    result = {
        **primary_summary,
        "summaries": summaries,
        "base_preco": " · ".join(labels),
        "source_priority": source_priority,
        "primary": {
            "source": str(primary_sel.get("source") or "sinapi").lower(),
            "uf": str(primary_sel.get("uf") or "SP").upper(),
            "reference": str(primary_sel.get("reference") or "").replace("/", "-"),
        },
    }
    _LOADED_FINGERPRINT = fingerprint
    _LOADED_RESULT = dict(result)
    return result


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
        metadata={"reference": reference, "uf": uf},
    )

    if provider_name == "sinapi" and rows:
        try:
            from pricing.budget.composition_index import get_composition_index

            index = get_composition_index()
            if index.is_current(rows, stem):
                pass
            elif len(rows) > 800:
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
