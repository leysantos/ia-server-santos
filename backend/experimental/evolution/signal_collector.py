"""
Signal Collector — captura sinais de execução para o Evolution Loop v1.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EvolutionSignal:
    source: str
    task_type: Optional[str] = None
    discipline: Optional[str] = None
    model_used: Optional[str] = None
    prompt_version: Optional[str] = None
    agent_version: Optional[str] = None
    agent_name: Optional[str] = None
    rag_context_length: int = 0
    rag_chunks_used: list[str] = field(default_factory=list)
    input_text: str = ""
    input_hash: str = ""
    output_quality: Optional[float] = None
    latency_ms: float = 0.0
    success: bool = True
    module: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "task_type": self.task_type,
            "discipline": self.discipline,
            "model_used": self.model_used,
            "prompt_version": self.prompt_version,
            "agent_version": self.agent_version,
            "agent_name": self.agent_name,
            "rag_context_length": self.rag_context_length,
            "rag_chunks_used": self.rag_chunks_used,
            "input_text": self.input_text[:500],
            "input_hash": self.input_hash,
            "output_quality": self.output_quality,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "module": self.module,
            "extra": self.extra,
        }


def _hash_input(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _extract_rag_info(extra: dict[str, Any]) -> tuple[int, list[str]]:
    rag = extra.get("rag") or {}
    length = int(rag.get("context_length") or 0)
    chunks = rag.get("chunks_used") or rag.get("normas") or []
    if isinstance(chunks, str):
        chunks = [chunks]
    return length, [str(c) for c in chunks[:20]]


def _extract_prompt_version(extra: dict[str, Any]) -> Optional[str]:
    tuned = extra.get("prompt_tuned") or {}
    return tuned.get("prompt_version") or extra.get("prompt_version")


class SignalCollector:
    """Normaliza payloads de chat, agent, copilot, aed, orchestrator e model eval."""

    def collect(self, execution_data: dict[str, Any]) -> EvolutionSignal:
        source = execution_data.get("source") or "unknown"
        extra = execution_data.get("extra") or execution_data.get("response", {}).get("extra") or {}
        if not isinstance(extra, dict):
            extra = {}

        input_text = (
            execution_data.get("input_text")
            or execution_data.get("input")
            or execution_data.get("text")
            or ""
        )
        rag_len, rag_chunks = _extract_rag_info(extra)

        response = execution_data.get("response") or {}
        quality = execution_data.get("output_quality")
        if quality is None:
            quality = execution_data.get("final_score")
        if quality is None and isinstance(response, dict):
            ev = response.get("evaluation") or {}
            quality = ev.get("final_score") if isinstance(ev, dict) else None

        return EvolutionSignal(
            source=source,
            task_type=execution_data.get("task_type"),
            discipline=execution_data.get("discipline") or response.get("discipline"),
            model_used=(
                execution_data.get("model_used")
                or extra.get("llm_model")
                or execution_data.get("winner_model")
            ),
            prompt_version=_extract_prompt_version(extra),
            agent_version=extra.get("agent_version") or execution_data.get("agent_version"),
            agent_name=execution_data.get("agent_name") or response.get("agent"),
            rag_context_length=rag_len or int(execution_data.get("rag_context_length") or 0),
            rag_chunks_used=rag_chunks or list(execution_data.get("rag_chunks_used") or []),
            input_text=input_text,
            input_hash=_hash_input(input_text),
            output_quality=float(quality) if quality is not None else None,
            latency_ms=float(execution_data.get("latency_ms") or 0.0),
            success=bool(execution_data.get("success", True)),
            module=execution_data.get("module"),
            extra={
                k: v
                for k, v in execution_data.items()
                if k not in ("response", "extra") and not callable(v)
            },
        )


def collect_agent_signal(
    route_result: dict[str, Any],
    response: dict[str, Any],
    *,
    latency_ms: float = 0.0,
) -> EvolutionSignal:
    extra = response.get("extra") or {}
    return SignalCollector().collect(
        {
            "source": "agent",
            "module": "dispatcher",
            "input_text": route_result.get("input") or response.get("input"),
            "discipline": response.get("discipline") or route_result.get("discipline"),
            "agent_name": response.get("agent"),
            "task_type": extra.get("sie", {}).get("system") if isinstance(extra.get("sie"), dict) else None,
            "latency_ms": latency_ms,
            "success": not response.get("error"),
            "extra": extra,
            "response": response,
        }
    )


def collect_model_evaluation_signal(eval_result: dict[str, Any], input_text: str) -> EvolutionSignal:
    return SignalCollector().collect(
        {
            "source": "model_evaluation",
            "module": "model_evaluation_loop",
            "input_text": input_text,
            "task_type": eval_result.get("task_type"),
            "model_used": eval_result.get("winner_model"),
            "winner_model": eval_result.get("winner_model"),
            "output_quality": eval_result.get("scores", {}).get("primary"),
            "latency_ms": eval_result.get("latency", {}).get("primary") or 0,
            "success": True,
            "extra": eval_result,
        }
    )
