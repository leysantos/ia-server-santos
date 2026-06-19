"""
RAG Evolution — ranking dinâmico de chunks, boosts de normas e cache de alto valor.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from config.settings import EVOLUTION_DATA_DIR

logger = logging.getLogger(__name__)

_store: Optional["RagEvolutionStore"] = None
_lock = threading.Lock()


class RagEvolutionStore:
    """Perfis de boost/penalidade por chunk ou norma — persistidos em JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"boosts": {}, "penalties": {}, "high_value_embeddings": []}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_boost(self, key: str) -> float:
        boosts = self._data.get("boosts") or {}
        return float(boosts.get(key, boosts.get(key.upper(), 0.0)))

    def get_penalty(self, key: str) -> float:
        penalties = self._data.get("penalties") or {}
        return float(penalties.get(key, penalties.get(key.upper(), 0.0)))

    def apply_boost(self, key: str, delta: float = 0.1, cap: float = 0.5) -> None:
        boosts = self._data.setdefault("boosts", {})
        current = float(boosts.get(key, 0.0))
        boosts[key] = round(min(cap, current + delta), 4)
        self._save()
        logger.info("RAG evolution boost %s -> %.3f", key, boosts[key])

    def apply_penalty(self, key: str, delta: float = 0.05, floor: float = -0.3) -> None:
        penalties = self._data.setdefault("penalties", {})
        current = float(penalties.get(key, 0.0))
        penalties[key] = round(max(floor, current - delta), 4)
        self._save()

    def record_high_value_embedding(self, chunk_signature: str, score: float) -> None:
        cache: list = self._data.setdefault("high_value_embeddings", [])
        entry = {"signature": chunk_signature, "score": score}
        if entry not in cache:
            cache.append(entry)
            self._data["high_value_embeddings"] = cache[-500:]
            self._save()

    def adjust_score(self, chunk_key: str, base_score: float) -> float:
        boost = self.get_boost(chunk_key)
        penalty = self.get_penalty(chunk_key)
        return max(0.0, min(1.0, base_score + boost + penalty))

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


def get_rag_evolution_store() -> RagEvolutionStore:
    global _store
    with _lock:
        if _store is None:
            _store = RagEvolutionStore(EVOLUTION_DATA_DIR / "rag_chunk_profiles.json")
        return _store


def apply_rag_score_evolution(
    hits: list[tuple[Any, float]],
) -> list[tuple[Any, float]]:
    """Re-ranqueia hits RAG com boosts aprendidos (opt-in via USE_EVOLUTION_LOOP)."""
    from config import settings

    if not settings.USE_EVOLUTION_LOOP:
        return hits

    store = get_rag_evolution_store()
    adjusted: list[tuple[Any, float]] = []
    for chunk, score in hits:
        key = chunk.metadata.get("norma") or chunk.source or chunk.id
        new_score = store.adjust_score(str(key), score)
        adjusted.append((chunk, new_score))
    adjusted.sort(key=lambda x: x[1], reverse=True)
    return adjusted
