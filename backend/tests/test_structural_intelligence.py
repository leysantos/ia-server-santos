"""Testes SIE v1 — Structural Intelligence Engine."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.structural_intelligence.structural_classifier import StructuralClassifier
from core.structural_intelligence.norms_selector import NormSelector
from core.structural_intelligence.model_selector import ModelSelector
from core.structural_intelligence.prompt_builder import PromptBuilder
from core.structural_intelligence.structural_engine import StructuralIntelligenceEngine
from core.structural_intelligence.dispatch_adapter import try_sie_dispatch


@pytest.fixture(autouse=True)
def _reset_model_router_singleton():
    """Isola mapa de modelos — outros testes podem alterar o singleton global."""
    import core.models.model_router as mr_mod

    mr_mod._router = None
    yield
    mr_mod._router = None


def test_case1_steel_industrial_40m():
    clf = StructuralClassifier()
    result = clf.classify("galpão metálico industrial 40m vão")

    assert result["system"] == "STEEL_STRUCTURE"
    assert result["span_estimate"] == 40.0
    assert result["complexity"] == "HIGH"

    norms = NormSelector().get_norms(result["system"])
    assert norms == ["NBR 8800", "NBR 14762", "NBR 6123"]

    model = ModelSelector().select(result["system"], result["complexity"])
    assert model == "gemma3:12b"


def test_case2_residential_concrete():
    clf = StructuralClassifier()
    result = clf.classify("residência em concreto armado")

    assert result["system"] == "CONCRETE_ARMED"
    assert result["complexity"] == "LOW"

    norms = NormSelector().get_norms(result["system"])
    assert norms == ["NBR 6118", "NBR 8681"]

    model = ModelSelector().select(result["system"], result["complexity"])
    assert model == "qwen2.5-coder:latest"


def test_case3_timber_light_roof():
    clf = StructuralClassifier()
    result = clf.classify("estrutura de madeira para cobertura leve")

    assert result["system"] == "TIMBER_STRUCTURE"
    norms = NormSelector().get_norms(result["system"])
    assert norms == ["NBR 7190"]

    model = ModelSelector().select(result["system"], result["complexity"])
    assert model == "qwen2.5-coder:latest"


def test_prompt_builder_includes_system_and_norms():
    engine = StructuralIntelligenceEngine()
    ctx, prompt = engine.process("residência em concreto armado")

    assert ctx.system == "CONCRETE_ARMED"
    assert "NBR 6118" in prompt
    assert "SISTEMA ESTRUTURAL" in prompt
    assert "residência em concreto armado" in prompt


def test_engine_full_pipeline():
    engine = StructuralIntelligenceEngine()
    ctx, prompt = engine.process(
        "galpão metálico industrial 40m vão",
        rag_context="NBR 8800 trechos relevantes",
    )

    assert ctx.system == "STEEL_STRUCTURE"
    assert ctx.model == "gemma3:12b"
    assert "NBR 8800" in ctx.norms
    assert "NBR 8800 trechos relevantes" in prompt


def test_dispatch_adapter_success():
    agent = MagicMock()
    agent.use_rag = False
    agent.retrieve_context.return_value = ""
    agent.llm_client.generate.return_value = ("Resposta técnica SIE", "gemma3:12b")
    agent.build_extra.return_value = {"normas_base": ["NBR 8800"]}
    agent.build_response.return_value = {
        "agent": "estruturas_agent",
        "discipline": "ESTRUTURAL",
        "result": "Resposta técnica SIE",
        "extra": {"sie": {}},
    }

    result = try_sie_dispatch(
        agent,
        "galpão metálico industrial 40m vão",
        use_rag=False,
    )

    assert result is not None
    agent.llm_client.generate.assert_called_once()
    call_kwargs = agent.llm_client.generate.call_args
    assert call_kwargs.kwargs.get("model") == "gemma3:12b" or call_kwargs[1].get("model") == "gemma3:12b"


def test_dispatch_adapter_fallback_on_failure():
    agent = MagicMock()
    agent.use_rag = False

    with patch(
        "core.structural_intelligence.structural_engine.StructuralIntelligenceEngine.process",
        side_effect=RuntimeError("SIE failure"),
    ):
        result = try_sie_dispatch(agent, "viga de concreto", use_rag=False)

    assert result is None
    agent.llm_client.generate.assert_not_called()


def test_dispatcher_estrutural_uses_sie():
    from core.dispatcher import dispatch

    mock_agent = MagicMock()
    mock_agent.handle.return_value = {"result": "fallback"}

    with patch("core.dispatcher.AGENTS", {"ESTRUTURAL": mock_agent}), patch(
        "core.dispatcher.USE_INTELLIGENT_AGENTS", True
    ), patch(
        "core.structural_intelligence.dispatch_adapter.try_sie_dispatch",
        return_value={"result": "sie_ok", "extra": {"sie": {"system": "STEEL_STRUCTURE"}}},
    ) as mock_sie:
        response = dispatch(
            {"discipline": "ESTRUTURAL", "input": "galpão metálico 40m", "_use_rag": False},
            persist=False,
        )

    mock_sie.assert_called_once()
    mock_agent.handle.assert_not_called()
    assert response["result"] == "sie_ok"


def test_dispatcher_other_disciplines_untouched():
    from core.dispatcher import dispatch

    mock_agent = MagicMock()
    mock_agent.handle.return_value = {"result": "hidraulico_ok"}

    with patch("core.dispatcher.AGENTS", {"HIDROSSANITÁRIO": mock_agent}), patch(
        "core.structural_intelligence.dispatch_adapter.try_sie_dispatch"
    ) as mock_sie:
        response = dispatch(
            {"discipline": "HIDROSSANITÁRIO", "input": "dimensionar reservatório"},
            persist=False,
        )

    mock_sie.assert_not_called()
    mock_agent.handle.assert_called_once()
    assert response["result"] == "hidraulico_ok"


if __name__ == "__main__":
    test_case1_steel_industrial_40m()
    test_case2_residential_concrete()
    test_case3_timber_light_roof()
    test_prompt_builder_includes_system_and_norms()
    test_engine_full_pipeline()
    test_dispatch_adapter_success()
    test_dispatch_adapter_fallback_on_failure()
    test_dispatcher_estrutural_uses_sie()
    test_dispatcher_other_disciplines_untouched()
    print("OK: testes SIE v1 passaram")
