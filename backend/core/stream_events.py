"""Helpers SSE (Server-Sent Events) para streaming de chat."""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any, Iterable, Iterator, TypeVar

T = TypeVar("T")


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_sse_keepalive() -> str:
    """Comentário SSE — evita buffering de proxy durante RAG/LLM longos."""
    return ": keepalive\n\n"


def iter_with_keepalive(
    source: Iterable[T],
    *,
    interval_sec: float = 12.0,
    keepalive_factory: Any = None,
) -> Iterator[T | Any]:
    """
    Consome `source` em thread e, se ficar ocioso > interval_sec, emite keepalive.

    Evita que Cloudflare / proxies mobile cortem SSE durante espera do primeiro token LLM.
    """
    q: queue.Queue[tuple[str, Any]] = queue.Queue()

    def _run() -> None:
        try:
            for item in source:
                q.put(("ok", item))
            q.put(("end", None))
        except Exception as exc:
            q.put(("err", exc))

    thread = threading.Thread(target=_run, daemon=True, name="sse-keepalive-source")
    thread.start()
    last_wait_note = 0.0

    while True:
        try:
            kind, payload = q.get(timeout=max(2.0, float(interval_sec)))
        except queue.Empty:
            now = time.monotonic()
            if keepalive_factory is not None and (now - last_wait_note) >= interval_sec:
                last_wait_note = now
                yield keepalive_factory()
            else:
                yield ("__sse_comment__", None)  # type: ignore[misc]
            continue

        if kind == "end":
            return
        if kind == "err":
            raise payload
        yield payload


def iter_text_chunks(text: str, chunk_size: int = 20) -> Iterator[str]:
    """Divide texto em pedaços para simular streaming quando não há iter_tokens."""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
