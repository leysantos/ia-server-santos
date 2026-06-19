"""Learning Loop v2 — auto-otimização de prompts por disciplina."""

from core.learning_v2.auto_tuner import AutoTuneReport, TuneResult, run_auto_tune, tune_discipline
from core.learning_v2.discipline_profiles import (
    build_empty_profile,
    get_latest_prompt_version,
    load_profile,
    list_profiles,
    prompt_key_for,
    save_profile,
)
from core.learning_v2.feedback_analyzer import (
    DisciplineAnalysis,
    fetch_and_analyze,
    analysis_to_dict,
)
from core.learning_v2.prompt_analyzer import analyze_prompt_gaps, get_base_instructions
from core.learning_v2.prompt_optimizer import (
    build_optimized_prompt,
    load_prompt_version,
    next_prompt_version,
    optimize_prompt_for_discipline,
)
from core.learning_v2.prompt_resolver import get_active_prompt_version, resolve_tuned_prompt

__all__ = [
    "AutoTuneReport",
    "TuneResult",
    "run_auto_tune",
    "tune_discipline",
    "build_empty_profile",
    "get_latest_prompt_version",
    "load_profile",
    "list_profiles",
    "prompt_key_for",
    "save_profile",
    "DisciplineAnalysis",
    "fetch_and_analyze",
    "analysis_to_dict",
    "analyze_prompt_gaps",
    "get_base_instructions",
    "build_optimized_prompt",
    "load_prompt_version",
    "next_prompt_version",
    "optimize_prompt_for_discipline",
    "get_active_prompt_version",
    "resolve_tuned_prompt",
]
