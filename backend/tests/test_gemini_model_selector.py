"""Testes: Gemini no seletor / override LLM."""

from __future__ import annotations

from unittest.mock import patch

from core.llm_override import (
    is_gemini_model,
    list_cloud_llm_models,
    normalize_llm_model_choice,
)


def test_is_gemini_model():
    assert is_gemini_model("gemini-3.6-flash")
    assert is_gemini_model("gemini")
    assert is_gemini_model("Gemini-3.6")
    assert not is_gemini_model("qwen3:8b")
    assert not is_gemini_model("auto")
    assert not is_gemini_model(None)


def test_normalize_gemini_alias():
    with patch(
        "core.inspection_report.gemini_client.resolve_gemini_model",
        return_value="gemini-3.6-flash",
    ):
        assert normalize_llm_model_choice("gemini") == "gemini-3.6-flash"
        assert normalize_llm_model_choice("auto") is None


def test_list_cloud_when_key_present():
    with (
        patch("core.inspection_report.gemini_client.gemini_available", return_value=True),
        patch(
            "core.inspection_report.gemini_client.resolve_gemini_model",
            return_value="gemini-3.6-flash",
        ),
    ):
        assert list_cloud_llm_models() == ["gemini-3.6-flash"]


def test_list_cloud_empty_without_key():
    with patch("core.inspection_report.gemini_client.gemini_available", return_value=False):
        assert list_cloud_llm_models() == []


def test_models_status_includes_gemini():
    from app.services.models_status_service import ModelsStatusService

    with (
        patch("app.services.models_status_service.fetch_installed_models", return_value=["qwen3:8b"]),
        patch(
            "app.services.models_status_service.list_cloud_llm_models",
            return_value=["gemini-3.6-flash"],
        ),
        patch("app.services.models_status_service.get_model_router") as mock_router,
        patch("app.services.models_status_service.list_performance_profiles", return_value=[]),
    ):
        mock_router.return_value.get_status.return_value = {
            "router_enabled": True,
            "installed_models": [],
        }
        status = ModelsStatusService().check()

    assert status["gemini_available"] is True
    assert "gemini-3.6-flash" in status["installed_models"]
    assert status["installed_models"][0] == "gemini-3.6-flash"
    assert status["cloud_models"] == ["gemini-3.6-flash"]


def test_ollama_client_generate_uses_gemini():
    from models.ollama_client import OllamaClient

    client = OllamaClient.__new__(OllamaClient)
    client.base_url = "http://localhost:11434"
    client.read_timeout = 60
    client.connect_timeout = 5
    client.primary_model = "qwen3:8b"
    client.fallback_model = None

    with (
        patch.object(client, "ping", return_value=True) as mock_ping,
        patch(
            "core.inspection_report.gemini_client.generate_text",
            return_value="resposta gemini",
        ) as mock_gen,
        patch.object(client, "_models_to_try", return_value=["gemini-3.6-flash"]),
    ):
        text, model = client.generate("oi", model="gemini-3.6-flash")

    assert text == "resposta gemini"
    assert model == "gemini-3.6-flash"
    mock_gen.assert_called_once()
    mock_ping.assert_not_called()


def test_ollama_client_stream_uses_gemini_stream():
    from models.ollama_client import OllamaClient

    client = OllamaClient.__new__(OllamaClient)
    client.base_url = "http://localhost:11434"
    client.primary_model = "qwen3:8b"
    client.fallback_model = None

    def fake_stream(*_a, **_k):
        yield "Olá "
        yield "mundo"

    with (
        patch.object(client, "_models_to_try", return_value=["gemini-3.6-flash"]),
        patch(
            "core.inspection_report.gemini_client.generate_text_stream",
            side_effect=fake_stream,
        ) as mock_stream,
        patch.object(client, "ping", return_value=True) as mock_ping,
    ):
        pieces = list(client.generate_stream("oi", model="gemini-3.6-flash"))

    assert pieces == [("Olá ", "gemini-3.6-flash"), ("mundo", "gemini-3.6-flash")]
    mock_stream.assert_called_once()
    mock_ping.assert_not_called()


def test_response_text_helper():
    from types import SimpleNamespace

    from core.inspection_report.gemini_client import _response_text

    assert _response_text(SimpleNamespace(text="abc", candidates=None)) == "abc"
    part = SimpleNamespace(text="xy")
    content = SimpleNamespace(parts=[part])
    cand = SimpleNamespace(content=content)
    assert _response_text(SimpleNamespace(text=None, candidates=[cand])) == "xy"


def test_models_to_try_keeps_gemini_not_in_ollama_list():
    """Regressão: Gemini era filtrado por list_models() do Ollama → caía no deepseek."""
    from models.ollama_client import OllamaClient

    client = OllamaClient.__new__(OllamaClient)
    client.primary_model = "qwen3:8b"
    client.fallback_model = "mistral:7b"

    with patch.object(
        client,
        "list_models",
        return_value=["deepseek-r1:14b", "qwen3:8b", "gemma4:latest"],
    ):
        resolved = client._models_to_try(
            "gemini-3.6-flash",
            ["deepseek-r1:14b", "qwen3:8b"],
        )

    assert resolved[0] == "gemini-3.6-flash"
    # Com primary Gemini, não deve anexar fallback_model Ollama automaticamente
    assert "mistral:7b" not in resolved or resolved[0] == "gemini-3.6-flash"


def test_engineering_stream_models_gemini_no_ollama_fallbacks():
    from core.models.engineering_model_routing import engineering_stream_models

    with patch(
        "core.models.engineering_model_routing.engineering_routing_enabled",
        return_value=True,
    ):
        model, fallbacks, tag = engineering_stream_models(
            "dimensionar viga",
            "ESTRUTURAL",
            llm_model="gemini-3.6-flash",
        )
    assert model == "gemini-3.6-flash"
    assert fallbacks == []
    assert tag == "user_override"
