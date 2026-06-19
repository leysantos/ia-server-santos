"""
Registry de sistemas estruturais suportados pelo Structural System Selector.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class StructuralSystem(str, Enum):
    CONCRETE_ARMED = "CONCRETE_ARMED"
    CONCRETE_PRESTRESSED = "CONCRETE_PRESTRESSED"
    PRECAST_CONCRETE = "PRECAST_CONCRETE"
    STEEL_STRUCTURE = "STEEL_STRUCTURE"
    TIMBER_STRUCTURE = "TIMBER_STRUCTURE"
    MIXED_SYSTEMS = "MIXED_SYSTEMS"


SYSTEM_REGISTRY: dict[StructuralSystem, dict[str, Any]] = {
    StructuralSystem.CONCRETE_ARMED: {
        "label": "Concreto Armado",
        "simulation_module": "concrete_armed_simulator",
        "materials": ["concreto", "aço CA-50", "aço CA-60"],
        "typical_use": ["residencial", "comercial baixa altura", "fundacoes"],
    },
    StructuralSystem.CONCRETE_PRESTRESSED: {
        "label": "Concreto Protendido",
        "simulation_module": "concrete_prestressed_simulator",
        "materials": ["concreto", "cabos protendidos", "aço ativo"],
        "typical_use": ["vãos médios", "lajes nervuradas", "pontes"],
    },
    StructuralSystem.PRECAST_CONCRETE: {
        "label": "Concreto Pré-moldado",
        "simulation_module": "precast_concrete_simulator",
        "materials": ["pré-moldado", "concreto industrializado"],
        "typical_use": ["industrial", "galpões", "modular"],
    },
    StructuralSystem.STEEL_STRUCTURE: {
        "label": "Estrutura Metálica",
        "simulation_module": "steel_structure_simulator",
        "materials": ["aço estrutural", "perfil metálico", "treliça"],
        "typical_use": ["grandes vãos", "industrial", "leveza estrutural"],
    },
    StructuralSystem.TIMBER_STRUCTURE: {
        "label": "Estrutura de Madeira",
        "simulation_module": "timber_structure_simulator",
        "materials": ["madeira", "CLT", "MDF estrutural"],
        "typical_use": ["leveza", "sustentabilidade", "baixa altura"],
    },
    StructuralSystem.MIXED_SYSTEMS: {
        "label": "Sistemas Mistas",
        "simulation_module": "mixed_systems_simulator",
        "materials": ["concreto + aço", "concreto + madeira"],
        "typical_use": ["edificios hibridos", "sinais conflitantes"],
    },
}


VALID_SYSTEMS = set(StructuralSystem)


def get_system_info(system: StructuralSystem) -> dict[str, Any]:
    return SYSTEM_REGISTRY[system]


def parse_system(raw: str) -> StructuralSystem | None:
    """Normaliza string para StructuralSystem."""
    if not raw:
        return None
    token = raw.strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "CONCRETE": StructuralSystem.CONCRETE_ARMED,
        "ARMED_CONCRETE": StructuralSystem.CONCRETE_ARMED,
        "PRESTRESSED": StructuralSystem.CONCRETE_PRESTRESSED,
        "PRECAST": StructuralSystem.PRECAST_CONCRETE,
        "STEEL": StructuralSystem.STEEL_STRUCTURE,
        "TIMBER": StructuralSystem.TIMBER_STRUCTURE,
        "WOOD": StructuralSystem.TIMBER_STRUCTURE,
        "MIXED": StructuralSystem.MIXED_SYSTEMS,
    }
    if token in aliases:
        return aliases[token]
    try:
        return StructuralSystem(token)
    except ValueError:
        for system in StructuralSystem:
            if system.value in token or system.name in token:
                return system
    return None
