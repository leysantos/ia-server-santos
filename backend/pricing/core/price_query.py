from __future__ import annotations

from pricing.models.price_item import PriceItem
from pricing.models.price_request import PriceRequest


def build_price_request(
    query: str,
    unit: str | None = None,
    region: str | None = None,
    source_priority: list[str] | None = None,
    limit: int = 10,
) -> PriceRequest:
    """Converte insumo estruturado (pós-LLM) em PriceRequest — sem preço."""
    return PriceRequest(
        query=query.strip(),
        unit=unit,
        region=region,
        source_priority=source_priority,
        limit=limit,
    )


def price_item_to_dict(item: PriceItem | None) -> dict | None:
    if item is None:
        return None
    return {
        "code": item.code,
        "description": item.description,
        "unit": item.unit,
        "price": item.price,
        "source": item.source,
        "region": item.region,
        "metadata": item.metadata,
    }
