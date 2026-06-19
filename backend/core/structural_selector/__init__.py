"""
Structural System Selector — camada de decisão de sistema estrutural (plugável).
"""

from core.structural_selector.norms_mapper import get_norm_set
from core.structural_selector.system_classifier import (
    StructuralSelection,
    select_structural_system,
)
from core.structural_selector.system_registry import StructuralSystem

__all__ = [
    "StructuralSystem",
    "StructuralSelection",
    "select_structural_system",
    "get_norm_set",
]
