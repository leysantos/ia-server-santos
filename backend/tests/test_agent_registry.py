import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_agent_names_match_registry():
    from core.agent_registry import DISCIPLINE_TO_AGENT, get_agent_name
    from core.dispatcher import AGENTS

    for discipline in AGENTS:
        assert discipline in DISCIPLINE_TO_AGENT
        assert get_agent_name(discipline) == DISCIPLINE_TO_AGENT[discipline]

    agent = AGENTS["ESTRUTURAL"]
    assert agent.name == "estruturas_agent"


if __name__ == "__main__":
    test_agent_names_match_registry()
    print("OK: registry consistente")
