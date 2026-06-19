"""Testes BaseAgentIntelligent (sem Ollama/RAG em runtime)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agents.base_agent_intelligent import BaseAgentIntelligent
from core.agents.estruturas_intelligent import EstruturasIntelligentAgent


class _TestAgent(BaseAgentIntelligent):
    def __init__(self, **kwargs):
        super().__init__(
            name="estruturas_agent",
            discipline="ESTRUTURAL",
            **kwargs,
        )


def test_build_prompt_includes_discipline_and_nbrs():
    agent = _TestAgent(use_rag=False, llm_client=MagicMock())
    prompt = agent.build_prompt("dimensionar viga", "NBR 6118: requisitos")

    assert "ESTRUTURAL" in prompt
    assert "NBR 6118" in prompt
    assert "CONTEXTO NORMATIVO RECUPERADO" in prompt
    assert "dimensionar viga" in prompt


def test_retrieve_context_uses_discipline():
    rag = MagicMock()
    rag.build_context.return_value = "contexto normativo"
    rag.indexed_chunks = 10

    agent = _TestAgent(rag_engine=rag, llm_client=MagicMock())
    context = agent.retrieve_context("viga de concreto")

    rag.build_context.assert_called_once_with(
        query="viga de concreto",
        discipline="ESTRUTURAL",
        doc_type="nbr",
    )
    assert context == "contexto normativo"


def test_handle_pipeline():
    rag = MagicMock()
    rag.build_context.return_value = "trecho NBR"
    rag.indexed_chunks = 5

    llm = MagicMock()
    llm.generate.return_value = ("Resposta técnica estruturada", "qwen3:14b")

    agent = _TestAgent(rag_engine=rag, llm_client=llm)
    response = agent.handle("dimensionar viga")

    assert response["discipline"] == "ESTRUTURAL"
    assert response["agent"] == "estruturas_agent"
    assert response["result"] == "Resposta técnica estruturada"
    assert response["extra"]["intelligent"] is True
    assert response["extra"]["llm_model"] == "qwen3:14b"
    assert response["extra"]["rag"]["active"] is True


def test_call_llm_fallback():
    llm = MagicMock()
    llm.generate.side_effect = [
        ("Resposta fallback", "qwen3-coder"),
    ]

    agent = _TestAgent(use_rag=False, llm_client=llm)
    result = agent.call_llm("prompt teste")

    assert "Resposta" in result
    assert agent._last_model_used == "qwen3-coder"


def test_estruturas_intelligent_agent_name():
    agent = EstruturasIntelligentAgent(use_rag=False, llm_client=MagicMock())
    assert agent.name == "estruturas_agent"
    assert agent.discipline == "ESTRUTURAL"


def test_base_agent_unchanged():
    from agents.base_agent import BaseAgent
    from agents.estruturas import EstruturasAgent

    legacy = EstruturasAgent()
    response = legacy.handle("viga", context=None)
    assert "simulada" in response["result"]
    assert not response.get("extra", {}).get("intelligent")


def test_build_prompt_uses_tuned_version_when_enabled():
    import tempfile
    from pathlib import Path

    import config.settings as settings_mod
    from core.learning_v2.prompt_analyzer import analyze_prompt_gaps
    from core.learning_v2.prompt_optimizer import optimize_prompt_for_discipline

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        profiles = tmp_path / "profiles"
        prompts = tmp_path / "prompts"
        profiles.mkdir()
        prompts.mkdir()

        settings_mod.LEARNING_V2_PROFILES_DIR = profiles
        settings_mod.LEARNING_V2_PROMPTS_DIR = prompts
        settings_mod.USE_TUNED_PROMPTS = True

        import core.learning_v2.discipline_profiles as profiles_mod
        import core.learning_v2.prompt_optimizer as optimizer_mod
        import core.agents.base_agent_intelligent as agent_mod

        profiles_mod.LEARNING_V2_PROFILES_DIR = profiles
        profiles_mod.LEARNING_V2_PROMPTS_DIR = prompts
        agent_mod.settings.USE_TUNED_PROMPTS = True

        from core.learning_v2.feedback_analyzer import DisciplineAnalysis

        analysis = DisciplineAnalysis(
            discipline="ESTRUTURAL",
            agent_name="estruturas_agent",
            feedback_sample_size=4,
            low_quality_count=2,
            common_errors=["faltou citar nbr 6118"],
            frequent_themes=["dimensionar viga"],
            error_patterns={},
            theme_counts={},
            avg_rating=2.5,
        )
        gap = analyze_prompt_gaps(analysis)
        optimize_prompt_for_discipline(
            discipline="ESTRUTURAL",
            gap_analysis=gap,
            common_errors=analysis.common_errors,
            frequent_themes=analysis.frequent_themes,
        )

        agent = _TestAgent(use_rag=False, llm_client=MagicMock())
        prompt = agent.build_prompt("dimensionar viga", "trecho NBR 6118")

        assert "prompt_estrutural_v1" in prompt
        assert "INSTRUÇÕES OTIMIZADAS (v1" in prompt
        assert "dimensionar viga" in prompt
        assert agent._last_prompt_meta["prompt_version"] == 1

        settings_mod.USE_TUNED_PROMPTS = False


def test_build_prompt_falls_back_without_tuned_prompt():
    from unittest.mock import MagicMock, patch

    import core.agents.base_agent_intelligent as agent_mod

    agent = _TestAgent(use_rag=False, llm_client=MagicMock())
    with patch.object(agent_mod.settings, "USE_TUNED_PROMPTS", True), patch(
        "core.learning_v2.prompt_resolver.resolve_tuned_prompt", return_value=None
    ):
        prompt = agent.build_prompt("dimensionar viga", "")

    assert "INSTRUÇÕES:" in prompt
    assert agent._last_prompt_meta is None


if __name__ == "__main__":
    test_build_prompt_includes_discipline_and_nbrs()
    test_retrieve_context_uses_discipline()
    test_handle_pipeline()
    test_call_llm_fallback()
    test_estruturas_intelligent_agent_name()
    test_base_agent_unchanged()
    test_build_prompt_uses_tuned_version_when_enabled()
    test_build_prompt_falls_back_without_tuned_prompt()
    print("OK: testes BaseAgentIntelligent passaram")
