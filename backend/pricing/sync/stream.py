"""SSE para importação de bases de preços com progresso."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Iterator
from typing import Any

from core.stream_events import format_sse

logger = logging.getLogger(__name__)


def sync_stream_events(
    service: Any,
    source: str,
    **options: Any,
) -> Iterator[str]:
    q: queue.Queue[tuple[str, Any]] = queue.Queue()

    def worker() -> None:
        try:

            def on_progress(data: dict[str, Any]) -> None:
                q.put(("progress", data))

            result = service.sync(source, on_progress=on_progress, **options)
            q.put(("done", result))
        except Exception as exc:
            logger.exception("Falha sync %s (stream)", source)
            q.put(("error", {"error": str(exc)}))

    threading.Thread(target=worker, daemon=True).start()

    while True:
        kind, payload = q.get()
        if kind == "progress":
            yield format_sse("progress", payload)
        elif kind == "done":
            yield format_sse("done", payload)
            break
        elif kind == "error":
            yield format_sse("error", payload)
            break
