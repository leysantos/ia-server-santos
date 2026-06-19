"""Testes Agent Generation Loop v1 (controlled)."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config.settings as settings_mod
from core.agent_generation.agent_evaluator import AgentEvaluator
from core.agent_generation.agent_proposer import AgentProposer
from core.agent_generation.agent_promotion_gate import AgentPromotionGate
from core.agent_generation.agent_registry_candidate import CandidateRegistry, CandidateAgent
from core.agent_generation.agent_simulator import AgentSimulator, SimulationReport, SimulationRun
from core.agent_generation.agent_generation_engine import (
    AgentGenerationEngine,
    emit_agent_generation_signal,
)
from core.agent_generation.constants import (
    ONLY_ALLOWED_DOMAINS,
    is_allowed_domain,
    normalize_domain,
    resolve_discipline,
)


def test_allowed_domains():
    assert "ESTRUTURAL" in ONLY_ALLOWED_DOMAINS
    assert is_allowed_domain("ESTRUTURAL")
    assert is_allowed_domain("HIDROSSANITÁRIO")
    assert not is_allowed_domain("CHAT")
    assert not is_allowed_domain("TELECOM")
    assert resolve_discipline("HIDROSSANITARIO") == "HIDROSSANITÁRIO"
    assert normalize_domain("ELÉTRICA") == "ELETRICA"


def test_proposer_never_duplicates_existing_agent():
    proposer = AgentProposer()
    proposals = proposer.propose_from_gaps(
        discipline="ESTRUTURAL",
        evolution_insight={"degradation_detected": True, "avg_score": 0.4},
    )
    names = [p.name for p in proposals]
    assert "estruturas_agent" not in names
    assert all(is_allowed_domain(p.discipline) for p in proposals)


def test_simulator_runs_within_bounds():
    simulator = AgentSimulator()
    candidate = CandidateAgent(
        name="estruturas_prestress_agent",
        discipline="ESTRUTURAL",
        version=1,
        purpose="Protendido",
        specialization="prestress",
        system_instructions="Especialista em protendido.",
        normas=["NBR 6118"],
    )
    proposal = {
        "name": candidate.name,
        "discipline": "ESTRUTURAL",
        "baseline_agent": "estruturas_agent",
    }
    report = simulator.run_sandbox(proposal, candidate, n_runs=25, use_llm=False)
    assert 20 <= report.run_count <= 50
    assert len(report.runs) == 25
    assert all(r.candidate_score >= 0 for r in report.runs)


def test_evaluator_detects_improvement():
    runs = [
        SimulationRun(i, "q", "base", "cand", 0.5, 0.7, 10, 12)
        for i in range(1, 21)
    ]
    report = SimulationReport("estruturas_prestress_agent", "ESTRUTURAL", "estruturas_agent", "estruturas_prestress_agent", 20, runs)
    result = AgentEvaluator().evaluate(report)
    assert result.improvement_over_baseline >= 0.08
    assert result.passed_improvement_gate


def test_promotion_gate_rejects_high_risk():
    gate = AgentPromotionGate()
    proposal = {
        "name": "estruturas_prestress_agent",
        "discipline": "ESTRUTURAL",
        "specialization": "prestress",
        "risk_score": 0.85,
    }
    from core.agent_generation.agent_evaluator import EvaluationResult

    evaluation = EvaluationResult(
        quality_score=0.8,
        consistency_score=0.9,
        avg_latency_ms=100,
        baseline_quality_score=0.6,
        improvement_over_baseline=0.15,
        run_count=30,
        passed_improvement_gate=True,
    )
    decision = gate.evaluate(proposal, evaluation)
    assert not decision.approved
    assert any("risk_score" in r for r in decision.reasons)


def test_promotion_gate_approves_good_candidate(tmp_path=None):
    with tempfile.TemporaryDirectory() as tmp:
        registry = CandidateRegistry(Path(tmp) / "candidates.json")
        proposal = {
            "name": "estruturas_prestress_agent",
            "discipline": "ESTRUTURAL",
            "specialization": "prestress",
            "risk_score": 0.35,
            "purpose": "Protendido",
            "baseline_agent": "estruturas_agent",
        }
        from core.agent_generation.agent_evaluator import EvaluationResult

        evaluation = EvaluationResult(
            quality_score=0.82,
            consistency_score=0.85,
            avg_latency_ms=120,
            baseline_quality_score=0.65,
            improvement_over_baseline=0.12,
            run_count=30,
            passed_improvement_gate=True,
        )
        with patch(
            "core.agent_generation.agent_promotion_gate.get_candidate_registry",
            return_value=registry,
        ):
            decision = AgentPromotionGate().evaluate(proposal, evaluation)
        assert decision.approved


def test_registry_never_exceeds_limits():
    with tempfile.TemporaryDirectory() as tmp:
        registry = CandidateRegistry(Path(tmp) / "candidates.json")
        with patch.object(registry, "count_total", return_value=25):
            ok, reason = registry.can_register_new()
            assert not ok
            assert "MAX_AGENTS_TOTAL" in reason


def test_engine_disabled_by_default():
    with patch.object(settings_mod, "USE_AGENT_GENERATION", False):
        result = AgentGenerationEngine().process_gap_signal({"discipline": "ESTRUTURAL"})
    assert result["status"] == "disabled"


def test_emit_signal_noop_when_disabled():
    with patch.object(settings_mod, "USE_AGENT_GENERATION", False):
        with patch(
            "core.agent_generation.agent_generation_engine.get_agent_generation_engine"
        ) as mock:
            emit_agent_generation_signal({"discipline": "ESTRUTURAL", "source": "agent"})
            mock.assert_not_called()


def test_full_pipeline_heuristic():
    with tempfile.TemporaryDirectory() as tmp:
        registry = CandidateRegistry(Path(tmp) / "candidates.json")
        with patch.object(settings_mod, "USE_AGENT_GENERATION", True), patch(
            "core.agent_generation.agent_generation_engine.get_candidate_registry",
            return_value=registry,
        ), patch(
            "core.agent_generation.agent_generation_engine.save_agent_proposal",
            return_value={"id": "test-id"},
        ), patch(
            "core.agent_generation.agent_generation_engine.save_agent_simulation",
            return_value={"id": "sim-id"},
        ), patch(
            "core.agent_generation.agent_generation_engine.update_agent_proposal_status",
            return_value={},
        ):
            engine = AgentGenerationEngine()
            engine.registry = registry
            result = engine.run_full_pipeline(
                {
                    "name": "estruturas_prestress_agent",
                    "discipline": "ESTRUTURAL",
                    "baseline_agent": "estruturas_agent",
                    "specialization": "prestress",
                    "purpose": "Protendido NBR 6118",
                    "risk_score": 0.35,
                    "dependencies": ["estruturas_agent"],
                },
                n_runs=20,
                use_llm=False,
            )
        assert result["status"] in ("approved_for_deployment", "rejected")
        assert "evaluation" in result
        assert "promotion" in result
