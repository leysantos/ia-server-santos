from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PriceItem:
    """Item de preço resolvido por um provider (insumo ou composição)."""

    code: str
    description: str
    unit: str
    price: float
    source: str
    region: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def cache_key(self) -> str:
        return f"{self.source}:{self.region or ''}:{self.code}"
