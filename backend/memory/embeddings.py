import logging
import threading
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
_EMBED_SERVER_ERROR_DELAYS = (2.0, 5.0, 10.0, 15.0)
_MIN_EMBED_INTERVAL = 0.15
_EMBED_BATCH_SIZE = 4

_throttle_lock = threading.Lock()
_last_embed_request_at = 0.0


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

    @staticmethod
    def _throttle() -> None:
        global _last_embed_request_at
        with _throttle_lock:
            now = time.monotonic()
            wait = _MIN_EMBED_INTERVAL - (now - _last_embed_request_at)
            if wait > 0:
                time.sleep(wait)
            _last_embed_request_at = time.monotonic()

    @staticmethod
    def _is_server_error(exc: Exception) -> bool:
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return exc.response.status_code >= 500
        text = str(exc).lower()
        return "500" in text or "502" in text or "503" in text

    def _retry_delay(self, attempt: int, exc: Exception) -> float:
        delays = _EMBED_SERVER_ERROR_DELAYS if self._is_server_error(exc) else _EMBED_RETRY_DELAYS
        return delays[min(attempt, len(delays) - 1)]

    def _prefix_for_task(self, task: str) -> str:
        return self.DOCUMENT_PREFIX if task == "document" else self.QUERY_PREFIX

    def _prepare_prompt(self, text: str, task: str) -> str:
        return self._truncate(f"{self._prefix_for_task(task)}{text}")

    def _cache_get(self, safe_text: str, task: str) -> list[float] | None:
        if not self.cache or not self.use_cache:
            return None
        return self.cache.get(safe_text, self.model, task)

    def _cache_set(self, safe_text: str, task: str, embedding: list[float]) -> None:
        if self.cache and self.use_cache:
            self.cache.set(safe_text, self.model, task, embedding)

    def _post_embed_batch(self, prompts: list[str]) -> list[list[float]]:
        self._throttle()
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": prompts},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(prompts):
            raise ValueError(
                f"Resposta Ollama /api/embed inválida: {len(embeddings or [])} vs {len(prompts)}"
            )
        return embeddings

    def _post_embed_single(self, prompt: str) -> list[float]:
        self._throttle()
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": prompt},
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def _embed_prompts_with_retry(self, prompts: list[str], task: str) -> list[list[float]]:
        last_error: Exception | None = None
        use_batch = len(prompts) > 1

        for attempt in range(_EMBED_RETRIES):
            try:
                if use_batch:
                    return self._post_embed_batch(prompts)
                return [self._post_embed_single(prompts[0])]
            except Exception as exc:
                last_error = exc
                delay = self._retry_delay(attempt, exc)
                if attempt < _EMBED_RETRIES - 1:
                    logger.debug(
                        "Ollama embed tentativa %d/%d falhou (%s); retry em %.1fs",
                        attempt + 1,
                        _EMBED_RETRIES,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                elif use_batch and len(prompts) > 1:
                    logger.warning(
                        "Batch embed falhou após %d tentativas; fallback item a item (%s)",
                        _EMBED_RETRIES,
                        exc,
                    )
                    return self._embed_prompts_sequential(prompts, task)

        assert last_error is not None
        raise last_error

    def _embed_prompts_sequential(self, prompts: list[str], task: str) -> list[list[float]]:
        results: list[list[float]] = []
        for prompt in prompts:
            last_error: Exception | None = None
            for attempt in range(_EMBED_RETRIES):
                try:
                    results.append(self._post_embed_single(prompt))
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    delay = self._retry_delay(attempt, exc)
                    if attempt < _EMBED_RETRIES - 1:
                        logger.debug(
                            "Ollama embed item tentativa %d/%d falhou (%s); retry em %.1fs",
                            attempt + 1,
                            _EMBED_RETRIES,
                            exc,
                            delay,
                        )
                        time.sleep(delay)
            if last_error is not None:
                raise last_error
        return results

    def _embed(self, text: str, task: str) -> list[float]:
        safe_text = self._prepare_prompt(text, task)

        cached = self._cache_get(safe_text, task)
        if cached is not None:
            self.last_cache_hit = True
            return cached

        self.last_cache_hit = False
        embedding = self._embed_prompts_with_retry([safe_text], task)[0]
        self._cache_set(safe_text, task, embedding)
        return embedding

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text, task="document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, task="query")

    def try_embed_document(self, text: str) -> list[float] | None:
        """Embed best-effort; retorna None após esgotar retries (indexação parcial)."""
        try:
            return self.embed_document(text)
        except Exception as exc:
            logger.warning("Embed documento ignorado após retries: %s", exc)
            return None

    def embed_batch(self, texts: list[str], task: str = "document") -> list[list[float]]:
        if not texts:
            return []
        optional = self.embed_batch_optional(texts, task=task)
        missing = sum(1 for item in optional if item is None)
        if missing:
            raise RuntimeError(f"Falha ao embedar {missing}/{len(texts)} textos em lote")
        return [item for item in optional if item is not None]

    def embed_batch_optional(
        self, texts: list[str], task: str = "document"
    ) -> list[list[float] | None]:
        """Embeddings em lote com cache, throttle e tolerância a falhas parciais."""
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        pending: list[tuple[int, str]] = []

        for index, text in enumerate(texts):
            safe_text = self._prepare_prompt(text, task)
            cached = self._cache_get(safe_text, task)
            if cached is not None:
                results[index] = cached
            else:
                pending.append((index, safe_text))

        for batch_start in range(0, len(pending), _EMBED_BATCH_SIZE):
            batch = pending[batch_start : batch_start + _EMBED_BATCH_SIZE]
            indices = [item[0] for item in batch]
            prompts = [item[1] for item in batch]
            try:
                embeddings = self._embed_prompts_with_retry(prompts, task)
            except Exception as exc:
                logger.warning(
                    "Lote embed %d-%d falhou (%s); tentando item a item",
                    batch_start + 1,
                    batch_start + len(batch),
                    exc,
                )
                for idx, prompt in zip(indices, prompts):
                    try:
                        embedding = self._embed_prompts_with_retry([prompt], task)[0]
                    except Exception as item_exc:
                        logger.warning("Chunk embed ignorado: %s", item_exc)
                        continue
                    results[idx] = embedding
                    self._cache_set(prompt, task, embedding)
                continue

            for idx, prompt, embedding in zip(indices, prompts, embeddings):
                results[idx] = embedding
                self._cache_set(prompt, task, embedding)

        return results

    def warmup(self) -> bool:
        """Pré-carrega o modelo de embedding no Ollama (best-effort)."""
        try:
            self.embed_query("warmup")
            return True
        except Exception as exc:
            logger.warning("Embed warmup falhou: %s", exc)
            return False
