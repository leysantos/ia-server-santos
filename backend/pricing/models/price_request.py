from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PriceRequest:
    """Consulta de preço — entrada do Pricing Engine (sem LLM no ranking)."""

    query: str
    unit: Optional[str] = None
    region: Optional[str] = None
    source_priority: Optional[list[str]] = None
    limit: int = 10
