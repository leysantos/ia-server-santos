"""Observabilidade RAG — queries fracas e métricas por disciplina."""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import RAG_OBSERVABILITY_LOG_PATH
from memory.rag_metrics import RAGMetrics


class RAGObserver:
    """Registra queries sem hits úteis e agrega latência por disciplina."""

    def __init__(self, log_path: Path = RAG_OBSERVABILITY_LOG_PATH):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._by_discipline: dict[str, list[float]] = defaultdict(list)

    def record(
        self,
        query: str,
        *,
        discipline: Optional[str] = None,
        domain: Optional[str] = None,
        hits_count: int = 0,
        metrics: Optional[RAGMetrics] = None,
    ) -> None:
        disc = discipline or "UNKNOWN"
        latency = metrics.total_rag_latency_ms if metrics else 0.0

        with self._lock:
            if metrics:
                self._by_discipline[disc].append(latency)

            if hits_count == 0:
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "query": query[:300],
                    "discipline": disc,
                    "domain": domain,
                    "hits_count": hits_count,
                    "metrics": metrics.log_summary() if metrics else {},
                }
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def discipline_stats(self) -> dict[str, dict[str, float]]:
        with self._lock:
            stats: dict[str, dict[str, float]] = {}
            for disc, latencies in self._by_discipline.items():
                if not latencies:
                    continue
                stats[disc] = {
                    "count": len(latencies),
                    "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
                    "max_latency_ms": round(max(latencies), 2),
                }
            return stats

    def failing_queries(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.log_path.is_file():
            return []
        lines = self.log_path.read_text(encoding="utf-8").strip().splitlines()
        result = []
        for line in lines[-limit:]:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return result


_observer: Optional[RAGObserver] = None
_observer_lock = threading.Lock()


def get_rag_observer() -> RAGObserver:
    global _observer
    with _observer_lock:
        if _observer is None:
            _observer = RAGObserver()
        return _observer
