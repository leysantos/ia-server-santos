from __future__ import annotations

import time
from typing import Any, Optional


class PriceCache:
    """Cache em memória com TTL opcional — performance para consultas repetidas."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def _key(self, key: str) -> str:
        return key.strip().lower()

    def get(self, key: str) -> Optional[Any]:
        k = self._key(key)
        entry = self._cache.get(k)
        if not entry:
            return None
        ts, value = entry
        if self.ttl_seconds and (time.time() - ts) > self.ttl_seconds:
            del self._cache[k]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._cache[self._key(key)] = (time.time(), value)

    def clear(self) -> None:
        self._cache.clear()
