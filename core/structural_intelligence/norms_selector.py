"""
Norm Selector — mapeia normas técnicas por sistema estrutural.
"""

from __future__ import annotations


class NormSelector:
    SYSTEM_NORMS: dict[str, list[str]] = {
        "CONCRETE_ARMED": ["NBR 6118", "NBR 8681"],
        "CONCRETE_PRESTRESSED": ["NBR 6118", "NBR 8681"],
        "STEEL_STRUCTURE": ["NBR 8800", "NBR 14762", "NBR 6123"],
        "TIMBER_STRUCTURE": ["NBR 7190"],
        "PRECAST_CONCRETE": ["NBR 9062", "NBR 6118"],
        "MIXED_SYSTEMS": ["NBR 6118", "NBR 8800", "NBR 6123"],
    }

    DEFAULT_NORMS = ["NBR 6118", "NBR 8681"]

    def get_norms(self, system: str) -> list[str]:
        return list(self.SYSTEM_NORMS.get(system, self.DEFAULT_NORMS))
