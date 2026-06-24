"""Testes — ajuste de modelo por VRAM e stream vazio Ollama."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.runtime.model_vram import fit_model_to_vram, model_fits_vram
from models.ollama_client import OllamaClient


def test_qwen36_does_not_fit_8gb_gpu():
    with patch("core.runtime.model_vram.gpu_total_vram_mb", return_value=8192.0):
        assert not model_fits_vram("qwen3.6:latest")


def test_fit_model_to_vram_demotes_qwen36_on_8gb():
    with patch("core.runtime.model_vram.gpu_total_vram_mb", return_value=8192.0):
        model, fallbacks, notice = fit_model_to_vram(
            "qwen3.6:latest",
            ["deepseek-r1:14b", "gemma4:latest", "mistral:7b"],
        )
    assert model == "gemma4:latest"
    assert notice is not None
    assert "qwen3.6" in notice


def test_ollama_stream_empty_tries_fallback():
    client = OllamaClient(primary_model="qwen3.6:latest", fallback_model="gemma4:latest", timeout=30)

    empty_done = json.dumps({"response": "", "done": True})
    ok_chunk = json.dumps({"response": "ok", "done": False})
    ok_done = json.dumps({"response": "", "done": True})

    responses = {
        "qwen3.6:latest": MagicMock(
            ok=True,
            iter_lines=MagicMock(return_value=[empty_done]),
            __enter__=lambda s: s,
            __exit__=MagicMock(return_value=False),
        ),
        "gemma4:latest": MagicMock(
            ok=True,
            iter_lines=MagicMock(return_value=[ok_chunk, ok_done]),
            __enter__=lambda s: s,
            __exit__=MagicMock(return_value=False),
        ),
    }

    def fake_post(url, json=None, timeout=None, stream=False):
        model = json["model"]
        return responses[model]

    with patch.object(client, "ping", return_value=True), patch.object(
        client, "list_models", return_value=["qwen3.6:latest", "gemma4:latest"]
    ), patch("models.ollama_client.requests.post", side_effect=fake_post):
        tokens = list(
            client.generate_stream(
                "prompt",
                model="qwen3.6:latest",
                fallback_models=["gemma4:latest"],
            )
        )

    assert tokens == [("ok", "gemma4:latest")]
