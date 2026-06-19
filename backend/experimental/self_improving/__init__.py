"""Self-Improving Loop v1 — meta-aprendizado sobre Evaluation Loop v2."""

from experimental.self_improving.system_insights import run_self_improving_loop, build_insights_report
from experimental.self_improving.meta_analyzer import analyze_meta
from experimental.self_improving.learning_strategy_engine import decide_strategies
from experimental.self_improving.patch_generator import generate_patches
from experimental.self_improving.patch_validator import validate_patch, validate_patches
from experimental.self_improving.failure_memory import record_failure, list_recent_failures

__all__ = [
    "run_self_improving_loop",
    "build_insights_report",
    "analyze_meta",
    "decide_strategies",
    "generate_patches",
    "validate_patch",
    "validate_patches",
    "record_failure",
    "list_recent_failures",
]
