"""Testes ModelRouter — roteamento centralizado de LLMs."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config.settings as settings_mod
from core.models.model_router import ModelRouter, get_model_router, routed_generate


def test_legacy_mode_uses_settings():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", False):
        router = ModelRouter()
        assert router.get_model("engineering_primary") == settings_mod.OLLAMA_LLM_MODEL
        assert router.get_model("chat_simple") == settings_mod.OLLAMA_CHAT_MODEL


def test_router_enabled_model_map():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", True):
        router = ModelRouter()
        assert router.get_model("engineering_primary") == "gemma3:12b"
        assert router.get_model("chat_natural") == "mistral:7b"
        assert router.get_model("chat_simple") == "phi3:mini"
        assert router.get_model("aed_simulation") == "gemma3:12b"


def test_is_light_task():
    router = ModelRouter()
    assert router.is_light_task("oi, bom dia!")
    assert router.is_light_task("obrigado")
    assert not router.is_light_task("dimensionar viga de concreto armado NBR 6118")


def test_is_engineering_task():
    router = ModelRouter()
    assert router.is_engineering_task("dimensionar viga", None)
    assert router.is_engineering_task("texto genérico", "ESTRUTURAL")
    assert not router.is_engineering_task("oi tudo bem", None)


def test_resolve_chat_task():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", True):
        router = ModelRouter()
        assert router.resolve_chat_task("oi") == "chat_simple"
        assert router.resolve_chat_task(
            "explique como funciona a plataforma de engenharia civil"
        ) == "chat_natural"


def test_engineering_fallback_chain():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", True):
        router = ModelRouter()
        fallbacks = router.get_fallback_models("engineering_primary")
        assert "qwen2.5-coder" in fallbacks[0]


def test_chat_natural_fallback_chain():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", True):
        router = ModelRouter()
        fallbacks = router.get_fallback_models("chat_natural")
        assert "phi3:mini" in fallbacks


def test_norms_steel_high_complexity_context():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", True):
        router = ModelRouter()
        task = router.resolve_engineering_task(
            "galpão metálico 40m",
            "ESTRUTURAL",
            complexity="HIGH",
        )
        model = router.get_model(task, {"complexity": "HIGH", "discipline": "ESTRUTURAL"})
        assert model == "gemma3:12b"


def test_routed_generate_records_inference():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", True):
        router = get_model_router()
        router._recent_requests.clear()
        router._active_by_module.clear()

        mock_client = MagicMock()
        mock_client.generate.return_value = ("resposta", "qwen3:14b")

        text, model = routed_generate(
            "prompt teste",
            "engineering_primary",
            module="test",
            discipline="ESTRUTURAL",
            client=mock_client,
        )

        assert text == "resposta"
        assert model == "qwen3:14b"
        assert len(router._recent_requests) == 1
        assert router._active_by_module.get("test") == "qwen3:14b"


def test_get_status_structure():
    router = ModelRouter()
    status = router.get_status(installed_models=["qwen3:14b", "mistral:7b"])
    assert "model_map" in status
    assert "active_by_module" in status
    assert "recent_requests" in status
    assert status["installed_models"] == ["qwen3:14b", "mistral:7b"]


def test_base_agent_legacy_unchanged_when_flag_off():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", False), patch.object(
        settings_mod, "USE_ENGINEERING_SMART_ROUTING", False
    ):
        from core.agents.base_agent_intelligent import BaseAgentIntelligent

        llm = MagicMock()
        llm.generate.return_value = ("ok", "qwen3:14b")
        agent = BaseAgentIntelligent(
            name="estruturas_agent",
            discipline="ESTRUTURAL",
            use_rag=False,
            llm_client=llm,
        )
        result = agent.call_llm("prompt", text="viga")
        assert result == "ok"
        llm.generate.assert_called_once_with("prompt")


if __name__ == "__main__":
    test_legacy_mode_uses_settings()
    test_router_enabled_model_map()
    test_is_light_task()
    test_is_engineering_task()
    test_resolve_chat_task()
    test_engineering_fallback_chain()
    test_chat_natural_fallback_chain()
    test_norms_steel_high_complexity_context()
    test_routed_generate_records_inference()
    test_get_status_structure()
    test_base_agent_legacy_unchanged_when_flag_off()
    print("OK: testes ModelRouter passaram")
