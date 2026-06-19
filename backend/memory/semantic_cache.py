"""Cache semântico de resultados RAG — reutiliza top-K por query similar."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from config.settings import (
    RAG_SEMANTIC_CACHE_MAX_ENTRIES,
    RAG_SEMANTIC_CACHE_THRESHOLD,
    SEMANTIC_CACHE_PATH,
)
from memory.models import DocumentChunk


@dataclass
class _CacheEntry:
    query_hash: str
    query_text: str
    discipline: str
    content_type: str
    embedding: list[float]
    hits: list[tuple[DocumentChunk, float]]


class SemanticQueryCache:
    """
    Cache de top-K por similaridade de embedding (cosine > threshold).
    Ring buffer em memória + persistência SQLite para warm-start.
    """

    def __init__(
        self,
        cache_path: Path = SEMANTIC_CACHE_PATH,
        threshold: float = RAG_SEMANTIC_CACHE_THRESHOLD,
        max_entries: int = RAG_SEMANTIC_CACHE_MAX_ENTRIES,
    ):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._ring: deque[_CacheEntry] = deque(maxlen=max_entries)
        self._init_db()
        self._load_recent()

    def _init_db(self) -> None:
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_hits (
                    query_hash TEXT PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    discipline TEXT,
                    content_type TEXT,
                    embedding TEXT NOT NULL,
                    hits_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _load_recent(self) -> None:
        if not self.cache_path.exists():
            return
        with sqlite3.connect(self.cache_path) as conn:
            rows = conn.execute(
                """
                SELECT query_hash, query_text, discipline, content_type,
                       embedding, hits_json
                FROM semantic_hits
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (self.max_entries,),
            ).fetchall()
        for row in reversed(rows):
            hits = self._deserialize_hits(json.loads(row[5]))
            self._ring.append(
                _CacheEntry(
                    query_hash=row[0],
                    query_text=row[1],
                    discipline=row[2] or "",
                    content_type=row[3] or "",
                    embedding=json.loads(row[4]),
                    hits=hits,
                )
            )

    @staticmethod
    def _make_hash(
        query: str,
        discipline: Optional[str],
        content_type: Optional[str],
    ) -> str:
        payload = f"{query.strip().lower()}|{discipline or ''}|{content_type or ''}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))

    @staticmethod
    def _serialize_hits(hits: list[tuple[DocumentChunk, float]]) -> list[dict]:
        return [
            {"chunk": chunk.to_dict(), "score": score}
            for chunk, score in hits
        ]

    @staticmethod
    def _deserialize_hits(data: list[dict]) -> list[tuple[DocumentChunk, float]]:
        result: list[tuple[DocumentChunk, float]] = []
        for item in data:
            chunk = DocumentChunk.from_dict(item["chunk"])
            result.append((chunk, float(item["score"])))
        return result

    def lookup(
        self,
        query: str,
        query_embedding: list[float],
        *,
        discipline: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Optional[list[tuple[DocumentChunk, float]]]:
        qhash = self._make_hash(query, discipline, content_type)
        disc = (discipline or "").upper()
        ct = (content_type or "").lower()

        with self._lock:
            for entry in reversed(self._ring):
                if entry.query_hash == qhash:
                    return list(entry.hits)
                if entry.discipline.upper() != disc:
                    continue
                if ct and entry.content_type.lower() != ct:
                    continue
                sim = self._cosine(query_embedding, entry.embedding)
                if sim >= self.threshold:
                    return list(entry.hits)
        return None

    def store(
        self,
        query: str,
        query_embedding: list[float],
        hits: list[tuple[DocumentChunk, float]],
        *,
        discipline: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> None:
        if not hits:
            return

        qhash = self._make_hash(query, discipline, content_type)
        entry = _CacheEntry(
            query_hash=qhash,
            query_text=query,
            discipline=(discipline or "").upper(),
            content_type=(content_type or "").lower(),
            embedding=query_embedding,
            hits=list(hits),
        )

        with self._lock:
            self._ring.append(entry)
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO semantic_hits
                    (query_hash, query_text, discipline, content_type, embedding, hits_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        qhash,
                        query[:500],
                        entry.discipline,
                        entry.content_type,
                        json.dumps(query_embedding),
                        json.dumps(self._serialize_hits(hits)),
                    ),
                )
                conn.commit()

    def count(self) -> int:
        with self._lock:
            return len(self._ring)
