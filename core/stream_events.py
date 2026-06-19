"""Helpers SSE (Server-Sent Events) para streaming de chat."""

from __future__ import annotations

import json
from typing import Any


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
