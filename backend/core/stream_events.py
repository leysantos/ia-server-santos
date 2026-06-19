"""Helpers SSE (Server-Sent Events) para streaming de chat."""

from __future__ import annotations

import json
from typing import Any, Iterator


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_sse_keepalive() -> str:
    """Comentário SSE — evita buffering de proxy durante RAG/LLM longos."""
    return ": keepalive\n\n"


def iter_text_chunks(text: str, chunk_size: int = 20) -> Iterator[str]:
    """Divide texto em pedaços para simular streaming quando não há iter_tokens."""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
