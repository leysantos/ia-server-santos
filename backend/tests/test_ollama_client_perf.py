"""Testes — cache e keep_alive do OllamaClient."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from models.ollama_client import OllamaClient, invalidate_ollama_client_cache


def test_list_models_cached():
    invalidate_ollama_client_cache()
    client = OllamaClient(timeout=10)
    fake = [{"name": "phi3:mini"}, {"name": "qwen3:14b"}]

    with patch("models.ollama_client.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"models": fake}
        mock_get.return_value = mock_resp

        first = client.list_models(force=True)
        second = client.list_models()

    assert first == ["phi3:mini", "qwen3:14b"]
    assert second == first
    assert mock_get.call_count == 1


def test_generate_includes_keep_alive():
    client = OllamaClient(timeout=10)
    client.primary_model = "phi3:mini"
    client.fallback_model = "mistral:7b"

    with patch.object(client, "ping", return_value=True):
        with patch.object(client, "list_models", return_value=["phi3:mini"]):
            with patch("models.ollama_client.requests.post") as mock_post:
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json.return_value = {"response": "ok"}
                mock_post.return_value = mock_resp

                text, model = client.generate("teste", model="phi3:mini")

    assert text == "ok"
    assert model == "phi3:mini"
    body = mock_post.call_args.kwargs["json"]
    assert body.get("keep_alive") == "15m"
    assert body["options"]["num_ctx"] == 8192
