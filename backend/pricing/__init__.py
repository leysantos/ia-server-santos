"""
Pricing Engine v1 — resolução determinística de preços (plugin providers).

Regra: IA interpreta intenção; Pricing Engine resolve preço. LLM nunca define preço final.
"""

from pricing.bootstrap import ensure_providers_registered
from pricing.core.pricing_engine import PricingEngine
from pricing.registry.provider_registry import ProviderRegistry

ensure_providers_registered()

__all__ = ["PricingEngine", "ProviderRegistry", "ensure_providers_registered"]
