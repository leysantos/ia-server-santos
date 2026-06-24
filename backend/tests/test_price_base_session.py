"""Testes — seleção de bases de preço na sessão de orçamento."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.bootstrap import ensure_providers_registered, reset_providers
from pricing.budget.price_bank_index import PriceBankIndex, PriceBankReferenceEntry
from pricing.budget.price_bank_store import CLOSED_NAME, PriceBankStore
from pricing.budget.price_base_session import apply_price_bases_selection
from pricing.core.price_query import build_price_request
from pricing.core.pricing_engine import PricingEngine
from pricing.registry.provider_registry import ProviderRegistry
from pricing.sync.sicro_parser import parse_sicro_folder
from pricing.sync.sicro_portal_resolver import sicro_reference_key

SICRO_SAMPLE = Path(__file__).resolve().parent.parent.parent / "bases-de-precos" / "am-01-2026"


def _seed_sicro_bank(ref: str, uf: str = "AM") -> None:
    if not SICRO_SAMPLE.is_dir():
        pytest.skip("amostra SICRO ausente")
    bank = parse_sicro_folder(SICRO_SAMPLE, uf=uf)
    store = PriceBankStore.for_reference(ref)
    store.root.mkdir(parents=True, exist_ok=True)
    closed_payload = [
        {
            "code": c.code,
            "description": c.description,
            "unit": c.unit,
            "price": c.price,
            "price_sem_desoneracao": c.price_sem_desoneracao,
            "regional": c.regional,
        }
        for c in bank["closed"]
    ]
    (store.root / CLOSED_NAME).write_text(json.dumps(closed_payload), encoding="utf-8")
    store.manifest_path.write_text(
        json.dumps(
            {
                "source": "cicro",
                "reference": ref,
                "uf": uf,
                "desonerado": True,
                "synced_at": "test",
                "counts": {"compositions_closed": len(closed_payload)},
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )


def _seed_sinapi_bank(ref: str, uf: str = "AM") -> None:
    store = PriceBankStore.for_reference(ref)
    store.root.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "code": "99999",
            "description": "Serviço SINAPI teste",
            "unit": "m2",
            "price": 10.0,
            "price_sem_desoneracao": 10.0,
            "regional": {uf: {"comd": 10.0, "semd": 10.0}},
        }
    ]
    (store.root / CLOSED_NAME).write_text(json.dumps(rows), encoding="utf-8")
    store.manifest_path.write_text(
        json.dumps(
            {
                "source": "sinapi",
                "reference": ref,
                "uf": uf,
                "desonerado": False,
                "synced_at": "test",
                "counts": {"compositions_closed": 1},
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_providers()
    yield
    reset_providers()


def test_apply_price_bases_loads_sinapi_and_cicro(tmp_path, monkeypatch):
    from pricing.budget import price_bank_index as pbi

    monkeypatch.setattr(pbi, "PRICE_BANK_ROOT", tmp_path / "price_bank")
    pbi.PRICE_BANK_ROOT.mkdir(parents=True, exist_ok=True)

    sinapi_ref = "BR-2026-05"
    cicro_ref = sicro_reference_key("AM", 2026, 1)
    _seed_sinapi_bank(sinapi_ref)
    _seed_sicro_bank(cicro_ref)

    idx = PriceBankIndex.load()
    idx.references = [
        PriceBankReferenceEntry(reference=sinapi_ref, source="sinapi", default_uf="AM"),
        PriceBankReferenceEntry(reference=cicro_ref, source="cicro", default_uf="AM"),
    ]
    idx.save()

    applied = apply_price_bases_selection(
        [
            {"enabled": True, "source": "sinapi", "label": "SINAPI", "uf": "AM", "reference": sinapi_ref},
            {"enabled": True, "source": "cicro", "label": "SICRO3", "uf": "AM", "reference": cicro_ref},
        ]
    )

    assert applied["source_priority"] == ["sinapi", "cicro"]
    ensure_providers_registered()
    sinapi = ProviderRegistry.get("sinapi")
    cicro = ProviderRegistry.get("cicro")
    assert sinapi is not None and sinapi.is_loaded
    assert cicro is not None and cicro.is_loaded
    assert any(str(r.get("code")) == "99999" for r in sinapi._data)  # noqa: SLF001
    assert any(str(r.get("code")) == "5214000" for r in cicro._data)  # noqa: SLF001

    engine = PricingEngine()
    hits = engine.resolve_many(
        build_price_request("5214000", source_priority=["cicro", "sinapi"], limit=5),
        best_only=False,
    )
    assert hits
    assert hits[0].code == "5214000"
    assert hits[0].source == "cicro"
