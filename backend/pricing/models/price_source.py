from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PriceSource:
    """Metadados de uma base de preços carregada por provider."""

    name: str
    label: str
    version: Optional[str] = None
    region: Optional[str] = None
    item_count: int = 0
    path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "version": self.version,
            "region": self.region,
            "item_count": self.item_count,
            "path": self.path,
            "metadata": self.metadata,
        }
