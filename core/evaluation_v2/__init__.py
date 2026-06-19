"""Evaluation Loop v2 — autoavaliação do Copilot v1."""

from core.evaluation_v2.evaluation_engine import evaluate
from core.evaluation_v2.evaluation_logger import run_evaluation_and_log, save_evaluation

__all__ = [
    "evaluate",
    "save_evaluation",
    "run_evaluation_and_log",
]
