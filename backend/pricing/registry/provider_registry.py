from __future__ import annotations

from typing import Iterator, Optional

from pricing.providers.base_provider import BasePriceProvider


class ProviderRegistry:
    """Registro plug-and-play de bases de preços."""

    _providers: dict[str, BasePriceProvider] = {}

    @classmethod
    def register(cls, provider: BasePriceProvider) -> None:
        cls._providers[provider.name] = provider

    @classmethod
    def get(cls, name: str) -> Optional[BasePriceProvider]:
        return cls._providers.get(name.lower())

    @classmethod
    def all(cls) -> list[BasePriceProvider]:
        return list(cls._providers.values())

    @classmethod
    def names(cls) -> list[str]:
        return sorted(cls._providers.keys())

    @classmethod
    def clear(cls) -> None:
        """Somente para testes."""
        cls._providers.clear()

    @classmethod
    def iter_priority(cls, priority_list: list[str] | None) -> Iterator[BasePriceProvider]:
        if priority_list:
            for name in priority_list:
                provider = cls.get(name)
                if provider and provider.is_loaded:
                    yield provider
            return
        for provider in cls.all():
            if provider.is_loaded:
                yield provider
