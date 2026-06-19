"""
Performance Analyzer — compara modelos, prompts e agentes por contexto.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from experimental.evolution.signal_collector import EvolutionSignal

logger = logging.getLogger(__name__)


@dataclass
class PerformanceInsight:
    context_key: str
    best_model: Optional[str] = None
    best_prompt_version: Optional[str] = None
    best_agent: Optional[str] = None
    win_rate: float = 0.0
    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    sample_count: int = 0
    degradation_detected: bool = False
    degradation_reason: Optional[str] = None
    model_rankings: list[dict[str, Any]] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_key": self.context_key,
            "best_model": self.best_model,
            "best_prompt_version": self.best_prompt_version,
            "best_agent": self.best_agent,
            "win_rate": self.win_rate,
            "avg_score": self.avg_score,
            "avg_latency_ms": self.avg_latency_ms,
            "sample_count": self.sample_count,
            "degradation_detected": self.degradation_detected,
            "degradation_reason": self.degradation_reason,
            "model_rankings": self.model_rankings,
            "opportunities": self.opportunities,
        }


class PerformanceAnalyzer:
    """Analisa sinais vs histórico PostgreSQL e perfis de modelo."""

    DEGRADATION_SCORE_DROP = 0.15

    def analyze(self, signal: EvolutionSignal) -> PerformanceInsight:
        context_key = self._context_key(signal)
        insight = PerformanceInsight(context_key=context_key)

        profiles = self._load_model_profiles(signal.task_type, signal.discipline)
        insight.model_rankings = profiles
        if profiles:
            best = profiles[0]
            insight.best_model = best.get("model_name")
            insight.win_rate = float(best.get("win_rate") or 0.0)
            insight.avg_score = float(best.get("avg_score") or 0.0)
            insight.avg_latency_ms = float(best.get("avg_latency_ms") or 0.0)
            insight.sample_count = int(best.get("total_evaluations") or 0)

        recent = self._recent_signals(context_key, limit=30)
        if recent:
            scores = [s.output_quality for s in recent if s.output_quality is not None]
            if scores:
                recent_avg = sum(scores) / len(scores)
                insight.avg_score = recent_avg
                if signal.output_quality is not None and recent_avg - signal.output_quality > self.DEGRADATION_SCORE_DROP:
                    insight.degradation_detected = True
                    insight.degradation_reason = "output_quality_below_recent_average"

        insight.opportunities = self._identify_opportunities(signal, insight)
        return insight

    @staticmethod
    def _context_key(signal: EvolutionSignal) -> str:
        parts = [
            signal.source or "unknown",
            signal.task_type or "general",
            signal.discipline or "GERAL",
        ]
        return ":".join(parts)

    def _load_model_profiles(
        self,
        task_type: Optional[str],
        discipline: Optional[str],
    ) -> list[dict[str, Any]]:
        if not task_type:
            return []
        try:
            from core.models.model_performance_service import list_performance_profiles

            rows = list_performance_profiles(task_type=task_type, limit=20)
            disc = discipline or "GERAL"
            filtered = [r for r in rows if r.get("discipline") == disc]
            return filtered or rows
        except Exception as exc:
            logger.debug("PerformanceAnalyzer profiles: %s", exc)
            return []

    def _recent_signals(self, context_key: str, limit: int = 30) -> list[EvolutionSignal]:
        try:
            from experimental.evolution.audit import list_recent_signals

            return list_recent_signals(context_key=context_key, limit=limit)
        except Exception:
            return []

    def _identify_opportunities(
        self,
        signal: EvolutionSignal,
        insight: PerformanceInsight,
    ) -> list[str]:
        ops: list[str] = []
        if insight.best_model and signal.model_used and insight.best_model != signal.model_used:
            ops.append(f"model_switch:{signal.model_used}->{insight.best_model}")
        if insight.degradation_detected:
            ops.append("quality_degradation_review")
        if signal.rag_context_length == 0 and signal.source in ("agent", "copilot", "aed"):
            ops.append("rag_empty_index_or_query")
        if signal.prompt_version and insight.best_prompt_version and signal.prompt_version != insight.best_prompt_version:
            ops.append(f"prompt_upgrade:{signal.prompt_version}->{insight.best_prompt_version}")
        return ops
