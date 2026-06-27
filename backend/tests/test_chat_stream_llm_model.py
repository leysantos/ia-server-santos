"""Testes — modelo LLM explícito no stream SSE (sem ContextVar)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.llm_override import llm_model_scope, normalize_llm_model_choice, resolve_llm_model
from core.runtime.ollama_concurrency import resolve_llm_stream_config


def test_normalize_llm_model_auto():
    assert normalize_llm_model_choice(None) is None
    assert normalize_llm_model_choice("auto") is None
    assert normalize_llm_model_choice("  gemma4:latest  ") == "gemma4:latest"


def test_resolve_llm_model_explicit_over_contextvar():
    with llm_model_scope("mistral:7b"):
        assert resolve_llm_model("gemma4:latest") == "gemma4:latest"
        assert resolve_llm_model(None) == "mistral:7b"


def test_stream_config_uses_explicit_llm_model(no_vram_downgrade):
    timeout, opts, fallbacks, _, _effective = resolve_llm_stream_config(
        primary_model="phi3:mini",
        llm_model="gemma4:latest",
    )
    assert timeout >= 300
    assert "num_gpu" not in opts
    assert len(fallbacks) >= 2


def test_chat_agent_iter_tokens_receives_llm_model(no_vram_downgrade):
    from agents.chat import ChatAgent

    agent = ChatAgent(use_llm=True)

    def fake_stream(prompt, model=None, fallback_models=None, options=None):
        assert model == "gemma4:latest"
        yield "Olá", "gemma4:latest"

    mock_client = MagicMock()
    mock_client.generate_stream = fake_stream

    with patch("agents.chat.OllamaClient", return_value=mock_client), patch.object(
        agent, "_client_for_runtime"
    ) as mock_runtime:
        mock_runtime.return_value = (mock_client, MagicMock(model_override=None, ollama_options={}))
        tokens = list(
            agent.iter_tokens(
                "explique a plataforma de engenharia civil detalhadamente",
                llm_model="gemma4:latest",
            )
        )
    assert tokens == ["Olá"]
    assert agent._last_model == "gemma4:latest"
