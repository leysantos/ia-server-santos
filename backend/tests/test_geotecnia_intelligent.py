"""Testes do agente geotécnico inteligente (prompt, sem Ollama)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agents.discipline_prompts import is_foundation_query
from core.agents.geotecnia_intelligent import GeotecniaIntelligentAgent
from core.agents.base_agent_intelligent import BaseAgentIntelligent


def test_geotecnia_prompt_includes_decision_instructions():
    agent = GeotecniaIntelligentAgent(use_rag=False, llm_client=MagicMock())
    query = "qual fundação para carga de 200t com tensão admissível 2,5 kg/cm²"
    prompt = agent.build_prompt(query, "NBR 6122: sapatas")

    assert "Solução recomendada" in prompt
    assert "A_min = P / σ_adm" in prompt
    assert "NBR 6122" in prompt
    assert "NBR 7185" in prompt
    assert "NÃO cite NBR 6118" in prompt
    assert "2,0 a 4,0" in prompt
    assert query in prompt


def test_geotecnia_agent_registered_name():
    agent = GeotecniaIntelligentAgent(use_rag=False, llm_client=MagicMock())
    assert agent.name == "geotecnia_agent"
    assert agent.discipline == "GEOTECNIA"


def test_foundation_query_detection():
    assert is_foundation_query("sapata para 200 toneladas")
    assert is_foundation_query("sondagem SPT fundação")
    assert not is_foundation_query("dimensionar viga NBR 6118")


def test_estrutural_gets_foundation_hint_on_foundation_query():
    from unittest.mock import MagicMock, patch

    agent = BaseAgentIntelligent(
        name="estruturas_agent",
        discipline="ESTRUTURAL",
        use_rag=False,
        llm_client=MagicMock(),
    )
    with patch("core.learning_v2.prompt_resolver.resolve_tuned_prompt", return_value=None):
        prompt = agent.build_prompt(
            "fundação sapata 200t sigma adm 2.5 kg/cm2",
            "",
        )
    assert "Solução recomendada" in prompt
    assert "A_min = P/σ_adm" in prompt


def test_estrutural_no_foundation_hint_on_beam_query():
    agent = BaseAgentIntelligent(
        name="estruturas_agent",
        discipline="ESTRUTURAL",
        use_rag=False,
        llm_client=MagicMock(),
    )
    prompt = agent.build_prompt("dimensionar viga biapoiada", "")
    assert "A_min = P/σ_adm" not in prompt


if __name__ == "__main__":
    test_geotecnia_prompt_includes_decision_instructions()
    test_geotecnia_agent_registered_name()
    test_foundation_query_detection()
    test_estrutural_gets_foundation_hint_on_foundation_query()
    test_estrutural_no_foundation_hint_on_beam_query()
    print("OK: testes geotecnia intelligent passaram")
