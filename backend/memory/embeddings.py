import logging
import time

import requests

from config.settings import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL
from memory.embedding_cache import EmbeddingCache

logger = logging.getLogger(__name__)

# nomic-embed-text no Ollama costuma rodar com contexto 2048 tokens (ver `ollama ps`).
# Chunks RAG podem ter até 1200 palavras — truncamos antes do embed para caber no modelo.
_MAX_EMBED_WORDS = 512
_MAX_EMBED_CHARS = 4000
_EMBED_RETRIES = 4
_EMBED_RETRY_DELAYS = (0.5, 1.5, 3.0, 6.0)


class NomicEmbedder:
    """
    Cliente de embeddings via Ollama (nomic-embed-text).
    Usa prefixos recomendados pelo modelo para documentos e consultas.
    """

    DOCUMENT_PREFIX = "search_document: "
    QUERY_PREFIX = "search_query: "

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_EMBED_MODEL,
        cache: EmbeddingCache | None = None,
        use_cache: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.use_cache = use_cache
        self.cache = cache if cache is not None else (EmbeddingCache() if use_cache else None)
        self.last_cache_hit = False

    @staticmethod
    def _truncate(text: str) -> str:
        words = text.split()
        if len(words) > _MAX_EMBED_WORDS:
            text = " ".join(words[:_MAX_EMBED_WORDS])
        if len(text) > _MAX_EMBED_CHARS:
            return text[:_MAX_EMBED_CHARS]
        return text

    def _embed(self, text: str, task: str) -> list[float]:
        safe_text = self._truncate(text)

        if self.cache and self.use_cache:
            cached = self.cache.get(safe_text, self.model, task)
            if cached is not None:
                self.last_cache_hit = True
                return cached

        self.last_cache_hit = False
        last_error: Exception | None = None

        for attempt in range(_EMBED_RETRIES):
            try:
                response = requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": safe_text},
                    timeout=90,
                )
                response.raise_for_status()
                embedding = response.json()["embedding"]

                if self.cache and self.use_cache:
                    self.cache.set(safe_text, self.model, task, embedding)

                return embedding
            except Exception as exc:
                last_error = exc
                delay = _EMBED_RETRY_DELAYS[min(attempt, len(_EMBED_RETRY_DELAYS) - 1)]
                logger.warning(
                    "Ollama embed tentativa %d/%d falhou (%s); retry em %.1fs",
                    attempt + 1,
                    _EMBED_RETRIES,
                    exc,
                    delay,
                )
                if attempt < _EMBED_RETRIES - 1:
                    time.sleep(delay)

        assert last_error is not None
        raise last_error

    def embed_document(self, text: str) -> list[float]:
        return self._embed(f"{self.DOCUMENT_PREFIX}{text}", task="document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed(f"{self.QUERY_PREFIX}{text}", task="query")

    def embed_batch(self, texts: list[str], task: str = "document") -> list[list[float]]:
        embed_fn = self.embed_document if task == "document" else self.embed_query
        return [embed_fn(text) for text in texts]

    def warmup(self) -> bool:
        """Pré-carrega o modelo de embedding no Ollama (best-effort)."""
        try:
            self.embed_query("warmup")
            return True
        except Exception as exc:
            logger.warning("Embed warmup falhou: %s", exc)
            return False
