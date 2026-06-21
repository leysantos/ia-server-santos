"""Testes — chat paralelo com GPU ocupada."""

from __future__ import annotations

from agents.chat import detect_intent, should_answer_with_template
from core.runtime.job_registry import get_job_registry
from core.runtime.ollama_concurrency import resolve_chat_runtime


def test_qual_seu_nome_uses_template_without_llm():
    intent = detect_intent("qual seu nome?")
    assert intent.name == "identity"
    assert should_answer_with_template("qual seu nome?", intent) is True


def test_resolve_chat_runtime_cpu_when_vision_active():
    registry = get_job_registry()
    job = registry.register(
        kind="vision",
        label="Análise visual (pci)",
        project_id="test",
        model="gemma3:12b",
    )
    try:
        plan = resolve_chat_runtime()
        assert plan.gpu_busy is True
        assert plan.active_vision_jobs >= 1
        assert plan.parallel_mode == "cpu_parallel"
        assert plan.ollama_options.get("num_gpu") == 0
        assert plan.timeout_sec >= 180
    finally:
        registry.finish(job.id, status="completed")
