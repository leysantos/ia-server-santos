from __future__ import annotations

from typing import Optional

from pricing.core.price_cache import PriceCache
from pricing.core.price_matcher import PriceMatcher
from pricing.models.price_item import PriceItem
from pricing.models.price_request import PriceRequest
from pricing.registry.provider_registry import ProviderRegistry


class PricingEngine:
    """
    Motor central de preços — fallback entre providers, ranking determinístico.
    LLM nunca define preço; apenas interpreta intenção fora deste módulo.
    """

    MIN_SIMILARITY = 0.35

    def __init__(self, cache: PriceCache | None = None) -> None:
        self.registry = ProviderRegistry
        self.cache = cache or PriceCache()
        self.matcher = PriceMatcher()

    def resolve(self, request: PriceRequest) -> Optional[PriceItem]:
        """Retorna melhor item ou None se nenhuma base tiver resultado."""
        results = self.resolve_many(request, best_only=True)
        return results[0] if results else None

    def resolve_many(
        self,
        request: PriceRequest,
        best_only: bool = False,
    ) -> list[PriceItem]:
        cache_key = self._cache_key(request, best_only)
        cached = self.cache.get(cache_key)
        if cached is not None:
            if best_only and cached:
                return [cached[0]]
            return cached

        collected: list[PriceItem] = []
        for provider in self.registry.iter_priority(request.source_priority):
            if not provider.is_loaded:
                continue
            results = provider.search(request)
            if not results:
                continue
            ranked = self._rank(results, request)
            collected.extend(ranked)
            if best_only and ranked:
                best = ranked[0]
                if self.matcher.similarity(request.query, best.description) < self.MIN_SIMILARITY:
                    continue
                self.cache.set(cache_key, ranked)
                return [best]

        if not collected:
            self.cache.set(cache_key, [])
            return []

        merged = self._rank(collected, request)
        self.cache.set(cache_key, merged)
        if best_only:
            return [merged[0]] if merged else []
        return merged[: request.limit]

    def get_by_code(self, source: str, code: str) -> Optional[PriceItem]:
        provider = self.registry.get(source)
        if not provider:
            return None
        return provider.get_by_code(code)

    def _get_priority(self, priority_list: list[str] | None) -> list:
        if priority_list:
            return [self.registry.get(p) for p in priority_list if self.registry.get(p)]
        return self.registry.all()

    def _rank(self, results: list[PriceItem], request: PriceRequest) -> list[PriceItem]:
        """Ranking determinístico: similaridade desc, preço asc, código asc."""
        return sorted(
            results,
            key=lambda x: (
                -self.matcher.match_score(request.query, x.description, request.unit, x.unit),
                x.price,
                x.code,
            ),
        )

    def _cache_key(self, request: PriceRequest, best_only: bool) -> str:
        priority = ",".join(request.source_priority or [])
        mode = "best" if best_only else "many"
        return f"{request.query}|{request.unit or ''}|{request.region or ''}|{priority}|{mode}"
