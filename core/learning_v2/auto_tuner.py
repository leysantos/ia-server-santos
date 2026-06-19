"""
Auto Tuner — job manual ou agendado para otimização de prompts por disciplina.

Fluxo:
  1. Ler agent_feedback (PostgreSQL)
  2. Analisar padrões por disciplina
  3. Gerar nova versão de prompt (imutável)
  4. Atualizar discipline profile
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from core.learning_v2.discipline_profiles import (
    build_empty_profile,
    load_profile,
    prompt_key_for,
    save_profile,
)
from core.learning_v2.feedback_analyzer import (
    DisciplineAnalysis,
    analysis_to_dict,
    fetch_and_analyze,
)
from core.learning_v2.prompt_analyzer import analyze_prompt_gaps
from core.learning_v2.prompt_optimizer import optimize_prompt_for_discipline

logger = logging.getLogger(__name__)


@dataclass
class TuneResult:
    discipline: str
    success: bool
    prompt_version: Optional[int] = None
    prompt_key: Optional[str] = None
    profile: Optional[dict[str, Any]] = None
    skipped_reason: Optional[str] = None
    analysis: Optional[dict[str, Any]] = None


@dataclass
class AutoTuneReport:
    results: list[TuneResult] = field(default_factory=list)
    tuned_count: int = 0
    skipped_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tuned_count": self.tuned_count,
            "skipped_count": self.skipped_count,
            "results": [
                {
                    "discipline": r.discipline,
                    "success": r.success,
                    "prompt_version": r.prompt_version,
                    "prompt_key": r.prompt_key,
                    "skipped_reason": r.skipped_reason,
                    "profile": r.profile,
                }
                for r in self.results
            ],
        }


def _should_tune(analysis: DisciplineAnalysis, min_feedback: int) -> tuple[bool, str]:
    if analysis.feedback_sample_size < min_feedback:
        return False, f"amostra insuficiente ({analysis.feedback_sample_size} < {min_feedback})"

    if analysis.low_quality_count == 0 and not analysis.common_errors:
        return False, "sem feedback negativo ou padrões de erro identificados"

    return True, ""


def tune_discipline(
    analysis: DisciplineAnalysis,
    *,
    min_feedback: int = 3,
    min_improvements: int = 1,
) -> TuneResult:
    """Otimiza prompt de uma disciplina com base na análise."""
    discipline = analysis.discipline
    should, reason = _should_tune(analysis, min_feedback)
    if not should:
        return TuneResult(
            discipline=discipline,
            success=False,
            skipped_reason=reason,
            analysis=analysis_to_dict(analysis),
        )

    gap = analyze_prompt_gaps(analysis)
    if len(gap.suggested_improvements) < min_improvements and analysis.low_quality_count < 2:
        return TuneResult(
            discipline=discipline,
            success=False,
            skipped_reason="sem melhorias suficientes derivadas do feedback",
            analysis=analysis_to_dict(analysis),
        )

    try:
        version, _, path = optimize_prompt_for_discipline(
            discipline=discipline,
            gap_analysis=gap,
            common_errors=analysis.common_errors,
            frequent_themes=analysis.frequent_themes,
        )
    except Exception as exc:
        logger.warning("Learning Loop v2: falha ao otimizar %s: %s", discipline, exc)
        return TuneResult(
            discipline=discipline,
            success=False,
            skipped_reason=str(exc),
            analysis=analysis_to_dict(analysis),
        )

    existing = load_profile(discipline)
    profile = existing or build_empty_profile(discipline, agent_name=analysis.agent_name)
    profile.update(
        {
            "discipline": discipline,
            "prompt_version": version,
            "prompt_key": prompt_key_for(discipline, version),
            "agent_name": analysis.agent_name,
            "common_errors": analysis.common_errors,
            "improvements": gap.suggested_improvements,
            "frequent_themes": analysis.frequent_themes,
            "feedback_sample_size": analysis.feedback_sample_size,
            "low_quality_count": analysis.low_quality_count,
            "avg_rating": analysis.avg_rating,
            "prompt_path": str(path),
            "gaps": gap.gaps,
        }
    )
    saved = save_profile(profile)

    return TuneResult(
        discipline=discipline,
        success=True,
        prompt_version=version,
        prompt_key=prompt_key_for(discipline, version),
        profile=saved,
        analysis=analysis_to_dict(analysis),
    )


def run_auto_tune(
    discipline: Optional[str] = None,
    *,
    min_feedback: int = 3,
    limit: int = 500,
) -> AutoTuneReport:
    """
    Job principal — analisa feedback e gera prompts versionados por disciplina.

    Pode ser executado manualmente (CLI) ou agendado (cron/systemd).
    """
    report = AutoTuneReport()
    analyses = fetch_and_analyze(discipline=discipline, limit=limit)

    if not analyses:
        logger.info("Learning Loop v2: nenhum feedback para analisar")
        return report

    for disc, analysis in sorted(analyses.items()):
        result = tune_discipline(analysis, min_feedback=min_feedback)
        report.results.append(result)
        if result.success:
            report.tuned_count += 1
            logger.info(
                "Learning Loop v2: %s → %s v%s",
                disc,
                result.prompt_key,
                result.prompt_version,
            )
        else:
            report.skipped_count += 1
            logger.info(
                "Learning Loop v2: %s ignorado — %s",
                disc,
                result.skipped_reason,
            )

    return report
