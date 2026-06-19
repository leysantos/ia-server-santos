"""Autonomous Engineering Designer v1."""

from core.aed.aed_orchestrator import run_aed
from core.aed.project_understanding import understand_project, ProjectUnderstanding
from core.aed.design_generator import generate_designs, DesignOption
from core.aed.engineering_simulator import simulate_designs, SimulationResult
from core.aed.comparison_engine import compare_solutions, ComparisonMatrix
from core.aed.selection_engine import select_best_solution, SelectionResult
from core.aed.report_generator import generate_report

__all__ = [
    "run_aed",
    "understand_project",
    "ProjectUnderstanding",
    "generate_designs",
    "DesignOption",
    "simulate_designs",
    "SimulationResult",
    "compare_solutions",
    "ComparisonMatrix",
    "select_best_solution",
    "SelectionResult",
    "generate_report",
]
