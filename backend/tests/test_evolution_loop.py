"""Testes Evolution Loop v1."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config.settings as settings_mod
from core.evolution.evolution_engine import EvolutionEngine, emit_evolution_signal
from core.evolution.mutation_engine import MutationEngine
from core.evolution.performance_analyzer import PerformanceAnalyzer, PerformanceInsight
from core.evolution.rollout_manager import RolloutManager
from core.evolution.signal_collector import EvolutionSignal, SignalCollector
from core.evolution.rag_evolution import RagEvolutionStore, apply_rag_score_evolution
from memory.models import DocumentChunk


def test_emit_evolution_signal_disabled():
    with patch.object(settings_mod, "USE_EVOLUTION_LOOP", False):
        with patch(
            "core.evolution.evolution_engine.get_evolution_engine"
        ) as mock_engine:
            emit_evolution_signal({"source": "chat", "input_text": "oi"})
            mock_engine.assert_not_called()


def test_signal_collector_normalizes_payload():
    collector = SignalCollector()
    signal = collector.collect(
        {
            "source": "copilot",
            "input_text": "dimensionar laje",
            "task_type": "orchestration_synthesis",
            "discipline": "ESTRUTURAL",
            "model_used": "qwen3:14b",
            "output_quality": 0.82,
            "latency_ms": 1200,
            "success": True,
            "extra": {
                "rag": {"context_length": 400, "normas": ["NBR 6118"]},
                "prompt_version": "v3",
            },
        }
    )
    assert signal.source == "copilot"
    assert signal.discipline == "ESTRUTURAL"
    assert signal.model_used == "qwen3:14b"
    assert signal.rag_context_length == 400
    assert signal.prompt_version == "v3"
    assert signal.input_hash
    assert signal.output_quality == 0.82


def test_performance_analyzer_opportunities():
    signal = EvolutionSignal(
        source="agent",
        task_type="engineering_primary",
        discipline="ESTRUTURAL",
        model_used="qwen3:14b",
        rag_context_length=0,
    )
    insight = PerformanceInsight(
        context_key="agent:engineering_primary:ESTRUTURAL",
        best_model="gemma3:12b",
        win_rate=0.72,
        sample_count=10,
    )
    analyzer = PerformanceAnalyzer()
    ops = analyzer._identify_opportunities(signal, insight)
    assert "model_switch:qwen3:14b->gemma3:12b" in ops
    assert "rag_empty_index_or_query" in ops


def test_mutation_engine_proposes_model_and_rag():
    signal = EvolutionSignal(
        source="agent",
        task_type="engineering_primary",
        discipline="ESTRUTURAL",
        model_used="qwen3:14b",
        rag_chunks_used=["NBR 6118"],
        success=True,
    )
    insight = PerformanceInsight(
        context_key="agent:engineering_primary:ESTRUTURAL",
        best_model="gemma3:12b",
        win_rate=0.7,
        sample_count=12,
        opportunities=["model_switch:qwen3:14b->gemma3:12b"],
    )
    proposals = MutationEngine().propose(signal, insight)
    types = {p.mutation_type for p in proposals}
    assert "MODEL" in types
    assert "RAG" in types
    model_props = [p for p in proposals if p.mutation_type == "MODEL"]
    assert any(p.proposed_value == "gemma3:12b" for p in model_props)


def test_rollout_never_applies_agent_mutation():
    from core.evolution.mutation_engine import MutationProposal

    proposal = MutationProposal(
        mutation_type="AGENT",
        mutation_key="agent:review:estruturas_agent",
        current_value="v1",
        proposed_value="review_pipeline_config",
        context_key="agent:engineering_primary:ESTRUTURAL",
        rationale="degradation",
        risk_score=0.9,
    )
    with patch.object(settings_mod, "USE_EVOLUTION_LOOP", True), patch(
        "core.evolution.audit.save_evolution_mutation", return_value={"id": "x"}
    ):
        result = RolloutManager()._process_one(proposal)
    assert result["applied"] is False
    assert result["status"] == "proposed_manual_review"


def test_rollout_shadow_rejects_low_sample():
    from core.evolution.mutation_engine import MutationProposal

    proposal = MutationProposal(
        mutation_type="MODEL",
        mutation_key="model:auto:engineering_primary",
        current_value="qwen3:14b",
        proposed_value="gemma3:12b",
        context_key="agent:engineering_primary:ESTRUTURAL",
        rationale="best performer",
        payload={"win_rate": 0.8, "sample_count": 2, "task_type": "engineering_primary"},
    )
    with patch.object(settings_mod, "USE_EVOLUTION_LOOP", True), patch.object(
        settings_mod, "USE_SAFE_ROLLOUT", True
    ), patch("core.evolution.audit.save_evolution_mutation", return_value={"id": "x"}):
        result = RolloutManager()._process_one(proposal)
    assert result["applied"] is False
    assert result["shadow_passed"] is False


def test_rag_evolution_boost_and_rerank():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = RagEvolutionStore(Path(tmp) / "rag_profiles.json")
        store.apply_boost("NBR 6118", delta=0.2)

        chunk_a = DocumentChunk(
            id="a",
            text="concreto armado",
            source="nbr6118.pdf",
            metadata={"norma": "NBR 6118"},
        )
        chunk_b = DocumentChunk(
            id="b",
            text="instalações",
            source="nbr5410.pdf",
            metadata={"norma": "NBR 5410"},
        )
        hits = [(chunk_b, 0.9), (chunk_a, 0.85)]

        with patch.object(settings_mod, "USE_EVOLUTION_LOOP", True), patch(
            "core.evolution.rag_evolution.get_rag_evolution_store", return_value=store
        ):
            ranked = apply_rag_score_evolution(hits)

        assert ranked[0][0].id == "a"
        assert ranked[0][1] > ranked[1][1]


def test_evolution_engine_processes_when_enabled():
    engine = EvolutionEngine()
    with patch.object(settings_mod, "USE_EVOLUTION_LOOP", True), patch.object(
        engine, "collector"
    ) as mock_collector, patch(
        "core.evolution.evolution_engine.save_execution_signal"
    ), patch.object(engine.analyzer, "analyze") as mock_analyze, patch.object(
        engine.mutations, "propose", return_value=[]
    ):
        mock_collector.collect.return_value = EvolutionSignal(source="chat")
        mock_analyze.return_value = PerformanceInsight(context_key="chat:general:CHAT")
        result = engine.process_execution_result({"source": "chat", "input_text": "oi"})
    assert result["status"] == "processed"
    assert result["mutations_proposed"] == 0
