"""Shim — implementação movida para experimental.evolution (loops desativados por padrão)."""

from experimental.evolution.evolution_engine import (
    EvolutionEngine,
    emit_evolution_signal,
    get_evolution_engine,
)
from experimental.evolution.signal_collector import EvolutionSignal, SignalCollector, collect_agent_signal

__all__ = [
    "EvolutionEngine",
    "EvolutionSignal",
    "SignalCollector",
    "collect_agent_signal",
    "emit_evolution_signal",
    "get_evolution_engine",
]
