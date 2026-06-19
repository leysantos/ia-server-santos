"""Shim — implementação em experimental.self_improving."""

from experimental.self_improving.system_insights import run_self_improving_loop, build_insights_report
from experimental.self_improving.meta_analyzer import analyze_meta
from experimental.self_improving.learning_strategy_engine import decide_strategies
from experimental.self_improving.patch_generator import generate_patches
from experimental.self_improving.patch_validator import validate_patch, validate_patches
from experimental.self_improving.failure_memory import record_failure, list_recent_failures
