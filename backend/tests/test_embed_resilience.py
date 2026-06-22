"""Testes — resiliência e batch de embeddings."""

from unittest.mock import patch

from memory.embeddings import NomicEmbedder


def test_try_embed_document_returns_none_on_failure():
    embedder = NomicEmbedder(use_cache=False)
    with patch.object(embedder, "embed_document", side_effect=RuntimeError("ollama down")):
        assert embedder.try_embed_document("texto") is None


def test_embed_batch_optional_all_success():
    embedder = NomicEmbedder(use_cache=False)
    with patch.object(
        embedder,
        "_embed_prompts_with_retry",
        side_effect=[[[0.1, 0.2], [0.3, 0.4]]],
    ):
        results = embedder.embed_batch_optional(["a", "b"], task="document")
    assert results == [[0.1, 0.2], [0.3, 0.4]]
