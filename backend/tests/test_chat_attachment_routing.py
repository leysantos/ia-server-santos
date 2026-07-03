"""Testes — roteamento de modelo por anexos do chat."""

from __future__ import annotations

from pathlib import Path

from core.chat.chat_attachment_routing import resolve_auto_llm_model_for_attachments


def test_resolve_vision_for_image():
    model = resolve_auto_llm_model_for_attachments(
        [Path("foto_obra.jpg")],
        installed_models={"gemma3:12b", "qwen3:14b"},
    )
    assert model == "gemma3:12b"


def test_resolve_cad_for_dxf():
    model = resolve_auto_llm_model_for_attachments(
        [Path("planta.dxf")],
        installed_models={"qwen3:14b", "gemma4:latest"},
    )
    assert model == "qwen3:14b"


def test_resolve_coder_for_py():
    model = resolve_auto_llm_model_for_attachments(
        [Path("script.py")],
        installed_models={"qwen2.5-coder", "phi3:mini"},
    )
    assert model == "qwen2.5-coder"


def test_resolve_none_without_paths():
    assert resolve_auto_llm_model_for_attachments([]) is None
