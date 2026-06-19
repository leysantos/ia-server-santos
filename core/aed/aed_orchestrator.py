"""
AED Orchestrator — pipeline principal do Autonomous Engineering Designer v1.

input → understanding → design generation → simulation → comparison → selection → report
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from core.aed.comparison_engine import compare_solutions
from core.aed.design_generator import generate_designs
from core.aed.engineering_simulator import simulate_designs
from core.aed.project_understanding import understand_project
from core.aed.report_generator import generate_report
from core.aed.selection_engine import select_best_solution
from core.structural_selector import select_structural_system

logger = logging.getLogger(__name__)


def run_aed(
    text: str,
    *,
    use_rag: bool = True,
    persist: bool = False,
    conversation_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Executa pipeline AED completo.

    Paralelo ao Copilot/Orchestrator — não altera agentes, RAG v2 nem dispatcher.
    """
    text = text.strip()
    if not text:
        raise ValueError("text não pode ser vazio")

    conv_id = conversation_id or str(uuid.uuid4())

    # 1. Understanding
    understanding = understand_project(text)
    logger.info(
        "aed understanding intent=%s disciplines=%s",
        understanding.intent,
        understanding.disciplines,
    )

    # 2. Design generation (≥2 opções por disciplina)
    designs = generate_designs(understanding)

    # 2.5 Structural System Selector (antes da simulação)
    structural_selection = select_structural_system(understanding)
    if structural_selection:
        logger.info(
            "aed structural_system=%s module=%s",
            structural_selection.structural_system,
            structural_selection.simulation_module,
        )

    # 3. Simulation
    simulations = simulate_designs(
        understanding,
        designs,
        use_rag=use_rag,
        structural_selection=structural_selection,
    )

    # 4. Comparison
    comparison = compare_solutions(designs, simulations)

    # 5. Selection
    selection = select_best_solution(understanding, designs, comparison, simulations)

    # 6. Report
    report = generate_report(
        understanding, designs, simulations, comparison, selection
    )

    output: dict[str, Any] = {
        "input": text,
        "conversation_id": conv_id,
        "understanding": understanding.to_dict(),
        "structural_selection": (
            structural_selection.to_dict() if structural_selection else None
        ),
        "designs": [d.to_dict() for d in designs],
        "simulations": [s.to_dict() for s in simulations],
        "comparison": comparison.to_dict(),
        "selection": selection.to_dict(),
        "report": report,
        "use_rag": use_rag,
    }

    if persist:
        saved = _persist_run(output)
        if saved:
            output["aed_run_id"] = saved.get("id")

    return output


def _persist_run(output: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        from core.aed.audit import save_aed_run
        return save_aed_run(output)
    except Exception as exc:
        logger.warning("AED: falha ao persistir run: %s", exc)
        return None
