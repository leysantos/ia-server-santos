"""Testes Structural System Selector v1."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.aed.project_understanding import understand_project
from core.aed.design_generator import generate_designs
from core.aed.engineering_simulator import simulate_designs
from core.aed.aed_orchestrator import run_aed
from core.structural_selector import select_structural_system, StructuralSystem
from core.structural_selector.norms_mapper import get_norm_set
from core.structural_selector.rules_based_selector import select_by_rules


def test_residential_selects_concrete():
    u = understand_project("dimensionar prédio residencial de baixa altura")
    sel = select_structural_system(u, use_llm_fallback=False)
    assert sel is not None
    assert sel.structural_system == StructuralSystem.CONCRETE_ARMED.value
    assert "NBR 6118" in sel.norm_set
    assert "NBR 8681" in sel.norm_set
    assert sel.simulation_module == "concrete_armed_simulator"
    assert sel.method == "rules"


def test_large_span_selects_steel():
    u = understand_project("dimensionar estrutura metálica com grande vão livre")
    rules = select_by_rules(u)
    assert rules.system == StructuralSystem.STEEL_STRUCTURE
    sel = select_structural_system(u, use_llm_fallback=False)
    assert sel.structural_system == StructuralSystem.STEEL_STRUCTURE.value
    assert "NBR 8800" in sel.norm_set


def test_industrial_steel_or_precast():
    u = understand_project("dimensionar galpão industrial pré-moldado estrutural")
    assert "ESTRUTURAL" in u.disciplines
    sel = select_structural_system(u, use_llm_fallback=False)
    assert sel is not None
    assert sel.structural_system in (
        StructuralSystem.PRECAST_CONCRETE.value,
        StructuralSystem.STEEL_STRUCTURE.value,
        StructuralSystem.MIXED_SYSTEMS.value,
    )


def test_timber_lightness():
    u = understand_project("estrutura de madeira com leveza estrutural")
    sel = select_structural_system(u, use_llm_fallback=False)
    assert sel.structural_system in (
        StructuralSystem.TIMBER_STRUCTURE.value,
        StructuralSystem.MIXED_SYSTEMS.value,
    )
    if sel.structural_system == StructuralSystem.TIMBER_STRUCTURE.value:
        assert "NBR 7190" in sel.norm_set


def test_norms_mapper():
    assert get_norm_set(StructuralSystem.PRECAST_CONCRETE) == ["NBR 9062", "NBR 6118"]
    assert get_norm_set(StructuralSystem.STEEL_STRUCTURE) == ["NBR 8800"]


def test_skipped_without_structural_discipline():
    u = understand_project("calcular vazão de esgoto NBR 8160")
    assert "ESTRUTURAL" not in u.disciplines
    sel = select_structural_system(u, use_llm_fallback=False)
    assert sel is None


def test_simulator_uses_structural_selection():
    u = understand_project("dimensionar viga de concreto armado residencial")
    designs = generate_designs(u)
    sel = select_structural_system(u, use_llm_fallback=False)
    with patch("core.aed.engineering_simulator.get_rag_engine") as mock_rag:
        mock_rag.return_value.build_context.return_value = "NBR 6118 NBR 8681"
        sims = simulate_designs(u, designs, use_rag=True, structural_selection=sel)

    structural_sims = [s for s in sims if s.discipline == "ESTRUTURAL"]
    assert structural_sims
    for s in structural_sims:
        assert s.structural_system == StructuralSystem.CONCRETE_ARMED.value
        assert s.simulation_module == "concrete_armed_simulator"


def test_aed_pipeline_includes_structural_selection():
    with patch("core.aed.engineering_simulator.get_rag_engine") as mock_rag:
        mock_rag.return_value.build_context.return_value = "NBR 6118"
        with patch(
            "core.structural_selector.system_classifier.select_by_llm"
        ) as mock_llm:
            result = run_aed(
                "dimensionar prédio residencial",
                use_rag=True,
                persist=False,
            )

    mock_llm.assert_not_called()
    assert result.get("structural_selection") is not None
    assert result["structural_selection"]["structural_system"] == "CONCRETE_ARMED"


if __name__ == "__main__":
    test_residential_selects_concrete()
    test_large_span_selects_steel()
    test_industrial_steel_or_precast()
    test_timber_lightness()
    test_norms_mapper()
    test_skipped_without_structural_discipline()
    test_simulator_uses_structural_selection()
    test_aed_pipeline_includes_structural_selection()
    print("OK: testes Structural System Selector passaram")
