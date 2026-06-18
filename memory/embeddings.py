import requests

from config.settings import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL
from memory.embedding_cache import EmbeddingCache


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

    def _embed(self, text: str, task: str) -> list[float]:
        if self.cache and self.use_cache:
            cached = self.cache.get(text, self.model, task)
            if cached is not None:
                return cached

        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=60,
        )
        response.raise_for_status()
        embedding = response.json()["embedding"]

        if self.cache and self.use_cache:
            self.cache.set(text, self.model, task, embedding)

        return embedding

    def embed_document(self, text: str) -> list[float]:
        return self._embed(f"{self.DOCUMENT_PREFIX}{text}", task="document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed(f"{self.QUERY_PREFIX}{text}", task="query")

    def embed_batch(self, texts: list[str], task: str = "document") -> list[list[float]]:
        embed_fn = self.embed_document if task == "document" else self.embed_query
        return [embed_fn(text) for text in texts]
