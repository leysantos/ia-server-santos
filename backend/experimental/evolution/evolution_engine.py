"""
Evolution Engine — orquestrador do Evolution Loop v1.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from config import settings
from experimental.evolution.audit import save_execution_signal
from experimental.evolution.mutation_engine import MutationEngine
from experimental.evolution.performance_analyzer import PerformanceAnalyzer
from experimental.evolution.rollout_manager import RolloutManager
from experimental.evolution.signal_collector import EvolutionSignal, SignalCollector

logger = logging.getLogger(__name__)

_engine: Optional["EvolutionEngine"] = None


class EvolutionEngine:
    """Pipeline: sinais → análise → mutações → rollout seguro."""

    def __init__(self) -> None:
        self.collector = SignalCollector()
        self.analyzer = PerformanceAnalyzer()
        self.mutations = MutationEngine()
        self.rollout = RolloutManager()

    @staticmethod
    def enabled() -> bool:
        return settings.USE_EVOLUTION_LOOP

    def process_execution_result(self, execution_data: dict[str, Any]) -> dict[str, Any]:
        """
        Recebe resultado de chat, copilot, aed, orchestrator, agent ou model eval.
        """
        if not self.enabled():
            return {"status": "disabled"}

        signal = self.collector.collect(execution_data)
        save_execution_signal(signal)

        insight = self.analyzer.analyze(signal)
        proposals = self.mutations.propose(signal, insight)
        rollout_results = self.rollout.process(proposals) if proposals else []

        result = {
            "status": "processed",
            "signal": signal.to_dict(),
            "insight": insight.to_dict(),
            "mutations_proposed": len(proposals),
            "rollout_results": rollout_results,
        }

        logger.info(
            "evolution_loop source=%s discipline=%s mutations=%d applied=%d",
            signal.source,
            signal.discipline,
            len(proposals),
            sum(1 for r in rollout_results if r.get("applied")),
        )

        try:
            from core.agent_generation.agent_generation_engine import emit_agent_generation_signal

            emit_agent_generation_signal({**signal.to_dict(), "insight": insight.to_dict()})
        except Exception:
            pass

        return result


def get_evolution_engine() -> EvolutionEngine:
    global _engine
    if _engine is None:
        _engine = EvolutionEngine()
    return _engine


def emit_evolution_signal(execution_data: dict[str, Any]) -> None:
    """Fire-and-forget — nunca quebra fluxo principal."""
    if not settings.USE_EVOLUTION_LOOP:
        return
    try:
        get_evolution_engine().process_execution_result(execution_data)
    except Exception as exc:
        logger.warning("Evolution Loop ignorado: %s", exc)
