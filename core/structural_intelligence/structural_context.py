"""
Structural Context — objeto de transporte entre módulos do SIE v1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StructuralContext:
    system: str
    subsystem: Optional[str]
    norms: list[str]
    model: str
    complexity: str
    confidence: float
    span_estimate: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "subsystem": self.subsystem,
            "norms": self.norms,
            "model": self.model,
            "complexity": self.complexity,
            "confidence": self.confidence,
            "span_estimate": self.span_estimate,
            "metadata": self.metadata,
        }
