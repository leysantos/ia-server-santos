"""
Mapeamento automático de normas por sistema estrutural.
"""

from __future__ import annotations

from core.structural_selector.system_registry import StructuralSystem

NORMS_BY_SYSTEM: dict[StructuralSystem, list[str]] = {
    StructuralSystem.CONCRETE_ARMED: ["NBR 6118", "NBR 8681"],
    StructuralSystem.CONCRETE_PRESTRESSED: ["NBR 6118", "NBR 8681"],
    StructuralSystem.PRECAST_CONCRETE: ["NBR 9062", "NBR 6118"],
    StructuralSystem.STEEL_STRUCTURE: ["NBR 8800"],
    StructuralSystem.TIMBER_STRUCTURE: ["NBR 7190"],
    StructuralSystem.MIXED_SYSTEMS: [
        "NBR 6118",
        "NBR 8681",
        "NBR 8800",
        "NBR 7190",
        "NBR 9062",
    ],
}


def get_norm_set(system: StructuralSystem) -> list[str]:
    """Retorna conjunto normativo para o sistema estrutural."""
    return list(NORMS_BY_SYSTEM.get(system, []))


def merge_with_discipline_norms(
    system: StructuralSystem,
    discipline_norms: list[str] | None = None,
) -> list[str]:
    """Combina normas do sistema com normas já mapeadas pela disciplina."""
    base = get_norm_set(system)
    if not discipline_norms:
        return base
    merged: list[str] = []
    for norm in base + discipline_norms:
        if norm not in merged:
            merged.append(norm)
    return merged
