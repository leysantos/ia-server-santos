"""
Agent Evaluator — quality, consistency, latency e improvement vs baseline.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from core.agent_generation.agent_simulator import SimulationReport, SimulationRun
from core.agent_generation.constants import IMPROVEMENT_THRESHOLD


@dataclass
class EvaluationResult:
    quality_score: float
    consistency_score: float
    avg_latency_ms: float
    baseline_quality_score: float
    improvement_over_baseline: float
    run_count: int
    passed_improvement_gate: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality_score": round(self.quality_score, 4),
            "consistency_score": round(self.consistency_score, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "baseline_quality_score": round(self.baseline_quality_score, 4),
            "improvement_over_baseline": round(self.improvement_over_baseline, 4),
            "run_count": self.run_count,
            "passed_improvement_gate": self.passed_improvement_gate,
            "details": self.details,
        }


class AgentEvaluator:
    """Avalia relatório de simulação sandbox."""

    def evaluate(self, report: SimulationReport) -> EvaluationResult:
        runs = report.runs
        if not runs:
            return EvaluationResult(
                quality_score=0.0,
                consistency_score=0.0,
                avg_latency_ms=0.0,
                baseline_quality_score=0.0,
                improvement_over_baseline=0.0,
                run_count=0,
                passed_improvement_gate=False,
                details={"error": "no_runs"},
            )

        candidate_scores = [r.candidate_score for r in runs]
        baseline_scores = [r.baseline_score for r in runs]
        candidate_latencies = [r.candidate_latency_ms for r in runs]

        quality = sum(candidate_scores) / len(candidate_scores)
        baseline_quality = sum(baseline_scores) / len(baseline_scores)
        improvement = (quality - baseline_quality) / max(baseline_quality, 0.01)
        consistency = self._consistency(candidate_scores)
        avg_latency = sum(candidate_latencies) / len(candidate_latencies)

        wins = sum(1 for r in runs if r.candidate_score > r.baseline_score)
        win_rate = wins / len(runs)

        return EvaluationResult(
            quality_score=quality,
            consistency_score=consistency,
            avg_latency_ms=avg_latency,
            baseline_quality_score=baseline_quality,
            improvement_over_baseline=improvement,
            run_count=len(runs),
            passed_improvement_gate=improvement >= IMPROVEMENT_THRESHOLD,
            details={
                "win_rate": round(win_rate, 4),
                "wins": wins,
                "improvement_threshold": IMPROVEMENT_THRESHOLD,
                "score_stddev": round(self._stddev(candidate_scores), 4),
            },
        )

    @staticmethod
    def _consistency(scores: list[float]) -> float:
        if len(scores) < 2:
            return 1.0 if scores else 0.0
        std = AgentEvaluator._stddev(scores)
        return max(0.0, min(1.0, 1.0 - std * 2))

    @staticmethod
    def _stddev(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        return statistics.pstdev(values)
