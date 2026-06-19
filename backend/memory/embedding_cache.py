import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Optional

from config.settings import EMBEDDING_CACHE_PATH


class EmbeddingCache:
    """
    Cache persistente de embeddings para evitar recomputação via Ollama.
    Chave: hash(model + task + text)
    """

    def __init__(self, cache_path: Path = EMBEDDING_CACHE_PATH):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    cache_key TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    task TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    @staticmethod
    def make_key(text: str, model: str, task: str) -> str:
        payload = f"{model}|{task}|{text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, text: str, model: str, task: str) -> Optional[list[float]]:
        key = self.make_key(text, model, task)
        with sqlite3.connect(self.cache_path) as conn:
            row = conn.execute(
                "SELECT embedding FROM embeddings WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def set(self, text: str, model: str, task: str, embedding: list[float]):
        key = self.make_key(text, model, task)
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO embeddings (cache_key, model, task, embedding)
                VALUES (?, ?, ?, ?)
                """,
                (key, model, task, json.dumps(embedding)),
            )
            conn.commit()

    def count(self) -> int:
        with sqlite3.connect(self.cache_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()
        return row[0] if row else 0

    def clear(self):
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("DELETE FROM embeddings")
            conn.commit()
