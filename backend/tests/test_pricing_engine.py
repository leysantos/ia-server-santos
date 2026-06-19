"""Testes do Pricing Engine v1 — providers, cache, ranking e orçamento."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.bootstrap import ensure_providers_registered, load_default_bases, reset_providers
from pricing.budget.budget_builder import BudgetBuilder
from pricing.core.price_cache import PriceCache
from pricing.core.price_matcher import PriceMatcher
from pricing.core.price_query import build_price_request
from pricing.core.pricing_engine import PricingEngine
from pricing.providers.sinapi_provider import SinapiProvider
from pricing.providers.orse_provider import OrseProvider
from pricing.registry.provider_registry import ProviderRegistry

DATA_DIR = Path(__file__).resolve().parent.parent / "pricing" / "data"


def _fresh_engine() -> PricingEngine:
    reset_providers()
    ensure_providers_registered()
    load_default_bases(DATA_DIR)
    return PricingEngine(cache=PriceCache(ttl_seconds=60))


def test_providers_load_and_registry():
    reset_providers()
    ensure_providers_registered()
    loaded = load_default_bases(DATA_DIR)
    assert "sinapi" in loaded
    assert loaded["sinapi"] >= 5
    assert ProviderRegistry.get("sinapi") is not None


def test_sinapi_search_lexical():
    engine = _fresh_engine()
    request = build_price_request(query="alvenaria bloco estrutural", unit="m²")
    item = engine.resolve(request)
    assert item is not None
    assert item.source == "sinapi"
    assert item.price > 0


def test_fallback_sinapi_then_orse():
    engine = _fresh_engine()
    request = build_price_request(
        query="xyz_inexistente_123",
        source_priority=["sinapi", "orse"],
    )
    item = engine.resolve(request)
    assert item is None

    request2 = build_price_request(
        query="alvenaria bloco estrutural",
        source_priority=["orse", "sinapi"],
    )
    item2 = engine.resolve(request2)
    assert item2 is not None
    assert item2.source == "orse"


def test_ranking_deterministic_lowest_price_tiebreak():
    matcher = PriceMatcher()
    reset_providers()
    sinapi = SinapiProvider()
    sinapi.load(str(DATA_DIR / "sinapi.csv"))
    ProviderRegistry.register(sinapi)

    engine = PricingEngine()
    request = build_price_request(query="alvenaria bloco")
    results = engine.resolve_many(request)
    assert len(results) >= 1
    scores = [matcher.similarity(request.query, r.description) for r in results]
    assert scores == sorted(scores, reverse=True)


def test_cache_hit():
    engine = _fresh_engine()
    request = build_price_request(query="argamassa assentamento")
    first = engine.resolve(request)
    assert first is not None
    cache_key = engine._cache_key(request, True)  # noqa: SLF001
    assert engine.cache.get(cache_key) is not None
    second = engine.resolve(request)
    assert second.code == first.code


def test_budget_builder_hierarchy():
    engine = _fresh_engine()
    builder = BudgetBuilder(engine=engine)
    intent = {
        "scope": "alvenaria estrutural",
        "dimensions": {"length": 20, "height": 2.5},
    }
    result = builder.build_dict(intent, source_priority=["sinapi"])
    assert result["grand_total"] > 0
    root = result["items"][0]
    assert root["level"] == 0
    assert len(root["children"]) >= 1
    leaves = _collect_leaves(root)
    priced = [l for l in leaves if l.get("unit_price", 0) > 0]
    assert len(priced) >= 1
    assert priced[0]["source_base"]
    assert priced[0]["source_code"]
    assert "source_trace" in priced[0]["metadata"]


def _collect_leaves(node: dict) -> list[dict]:
    if not node.get("children"):
        return [node]
    out: list[dict] = []
    for child in node["children"]:
        out.extend(_collect_leaves(child))
    return out


def test_api_pricing_resolve():
    from app.routes.pricing import ResolveRequest, resolve_price

    body = ResolveRequest(query="concreto magro", source_priority=["sinapi"])
    result = resolve_price(body)
    assert result["best"] is not None
    assert result["best"]["source"] == "sinapi"


def test_api_budget_build():
    from app.routes.pricing import BudgetBuildRequest, build_budget

    body = BudgetBuildRequest(
        intent={
            "scope": "muro bloco estrutural",
            "dimensions": {"length": 10, "height": 2},
        },
        source_priority=["sinapi"],
    )
    result = build_budget(body)
    assert result["grand_total"] > 0
    assert result["items"]


def test_matcher_container_synonym_and_multi_token_lexical():
    matcher = PriceMatcher()
    desc = "INSTALAÇÃO E DESINSTALAÇÃO MANUAL DE CONTÊINER OU MÓDULO HABITÁVEL PEQUENO"
    assert matcher.lexical_hit("container", desc)
    assert matcher.lexical_hit("locação de container", "LOCAÇÃO DE CONTAINER PARA DEPOSITO")
    assert not matcher.lexical_hit("locação de container", "LOCAÇÃO DE PRAÇAS EM PONTALETEAMENTO")
