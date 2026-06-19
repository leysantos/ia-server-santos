"""Testes de performance e index-first do RAG v2."""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk
from memory.rag_runtime import is_rag_query_active, rag_query_context
from memory.reranker import light_rerank
from memory.retriever import Retriever
from memory.semantic_cache import SemanticQueryCache


def test_rag_query_context_active():
    assert is_rag_query_active() is False
    with rag_query_context():
        assert is_rag_query_active() is True
    assert is_rag_query_active() is False


def test_retrieve_no_pdf_read_at_query_time():
    """Query RAG não deve abrir PDF — apenas FAISS em memória."""
    with tempfile.TemporaryDirectory() as tmp:
        index_dir = Path(tmp) / "faiss_index"
        store = FaissVectorStore(index_dir=index_dir)
        store.add(
            DocumentChunk(
                text="concreto armado dimensionamento",
                embedding=[1.0, 0.0, 0.0],
                discipline="ESTRUTURAL",
                doc_type="nbr",
                metadata={"content_type": "nbrs"},
            )
        )
        store.save()

        reloaded = FaissVectorStore(index_dir=index_dir)

        class FakeEmbedder:
            last_cache_hit = True

            def embed_query(self, _q):
                return [1.0, 0.0, 0.0]

        retriever = Retriever(
            store=reloaded,
            embedder=FakeEmbedder(),
            semantic_cache=None,
            min_score=0.0,
        )

        pdf_open = patch(
            "memory.pdf_indexer.PDFIndexer.extract_text",
            side_effect=AssertionError("PDF read in runtime"),
        )

        with pdf_open:
            hits = retriever.retrieve(
                "dimensionar viga concreto",
                discipline="ESTRUTURAL",
                doc_type="nbr",
            )
        assert len(hits) >= 1
        assert retriever.last_metrics.hits_count >= 1


def test_semantic_cache_hit():
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "semantic.db"
        cache = SemanticQueryCache(cache_path=cache_path, threshold=0.92)

        emb = [1.0, 0.0, 0.0]
        hits = [
            (
                DocumentChunk(text="norma concreto", discipline="ESTRUTURAL"),
                0.95,
            )
        ]
        cache.store("query a", emb, hits, discipline="ESTRUTURAL", content_type="nbrs")

        similar = [0.99, 0.01, 0.0]
        cached = cache.lookup(
            "query similar",
            similar,
            discipline="ESTRUTURAL",
            content_type="nbrs",
        )
        assert cached is not None
        assert cached[0][0].text == "norma concreto"


def test_semantic_cache_exact_hash():
    with tempfile.TemporaryDirectory() as tmp:
        cache = SemanticQueryCache(cache_path=Path(tmp) / "sem.db")
        emb = [0.5, 0.5, 0.0]
        hits = [(DocumentChunk(text="x"), 0.8)]
        cache.store("exact query", emb, hits, discipline="ORÇAMENTO")

        result = cache.lookup("exact query", [0.0, 1.0, 0.0], discipline="ORÇAMENTO")
        assert result is not None
        assert result[0][0].text == "x"


def test_light_rerank_boosts_discipline():
    hits = [
        (DocumentChunk(text="a", discipline="ESTRUTURAL"), 0.5),
        (DocumentChunk(text="b", discipline="ELÉTRICA"), 0.55),
    ]
    reranked = light_rerank(hits, query="viga", discipline="ESTRUTURAL")
    assert reranked[0][0].discipline == "ESTRUTURAL"


def test_metadata_content_type_filter():
    with tempfile.TemporaryDirectory() as tmp:
        store = FaissVectorStore(index_dir=Path(tmp) / "idx")
        store.add(
            DocumentChunk(
                text="sinapi custo",
                embedding=[1.0, 0.0, 0.0],
                metadata={"content_type": "sinapi"},
            )
        )
        store.add(
            DocumentChunk(
                text="nbr concreto",
                embedding=[0.99, 0.01, 0.0],
                metadata={"content_type": "nbrs"},
            )
        )

        hits = store.search(
            [1.0, 0.0, 0.0],
            top_k=5,
            content_type="nbrs",
            min_score=0.0,
        )
        assert len(hits) == 1
        assert hits[0][0].metadata["content_type"] == "nbrs"


def test_multi_index_single_embed():
    """search_many deve embeddar query uma vez para N bases."""
    embed_calls = []

    class CountingEmbedder:
        last_cache_hit = False

        def embed_query(self, q):
            embed_calls.append(q)
            return [1.0, 0.0, 0.0]

    with tempfile.TemporaryDirectory() as tmp:
        with patch(
            "core.knowledge.multi_index_store.KNOWLEDGE_INDEX_DIR",
            Path(tmp) / "knowledge",
        ), patch(
            "core.knowledge.multi_index_store.KNOWLEDGE_INDEX_NAMES",
            {"nbr": "nbr_index", "sinapi": "cost_index"},
        ):
            from core.knowledge.multi_index_store import MultiIndexKnowledgeStore

            store = MultiIndexKnowledgeStore(embedder=CountingEmbedder())
            store.semantic_cache = None

            for base, name in [("nbr", "nbr_index"), ("sinapi", "cost_index")]:
                fs = store.get_store(base)
                fs.add(
                    DocumentChunk(
                        text=f"doc {base}",
                        embedding=[1.0, 0.0, 0.0],
                        metadata={"content_type": base},
                    )
                )

            hits = store.search_many(
                ["nbr", "sinapi"],
                "custo obra",
                top_k=5,
            )
            assert len(embed_calls) == 1
            assert len(hits) >= 1
            assert store.last_metrics.embedding_time_ms >= 0


def test_retrieval_performance_under_limit():
    """Retrieval local (FAISS + fake embed) deve ficar abaixo de 800ms."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FaissVectorStore(index_dir=Path(tmp) / "idx")
        for i in range(50):
            vec = np.random.randn(768).astype(np.float32)
            vec = (vec / np.linalg.norm(vec)).tolist()
            store.add(
                DocumentChunk(
                    text=f"chunk {i} concreto armado",
                    embedding=vec,
                    discipline="ESTRUTURAL",
                    doc_type="nbr",
                )
            )

        class FastEmbedder:
            last_cache_hit = True

            def embed_query(self, _):
                return [1.0] + [0.0] * 767

        retriever = Retriever(
            store=store,
            embedder=FastEmbedder(),
            semantic_cache=None,
            min_score=0.0,
        )

        start = time.perf_counter()
        for _ in range(10):
            retriever.retrieve("viga concreto", discipline="ESTRUTURAL")
        elapsed_ms = (time.perf_counter() - start) * 1000 / 10

        assert elapsed_ms < 800, f"avg latency {elapsed_ms:.1f}ms > 800ms"
        assert retriever.last_metrics.total_rag_latency_ms < 800


def test_faiss_consistent_results():
    with tempfile.TemporaryDirectory() as tmp:
        store = FaissVectorStore(index_dir=Path(tmp) / "idx")
        store.add(
            DocumentChunk(
                text="NBR 6118 concreto",
                embedding=[1.0, 0.0, 0.0],
                metadata={"nbr_code": "6118"},
            )
        )
        store.save()
        reloaded = FaissVectorStore(index_dir=Path(tmp) / "idx")

        h1 = reloaded.search([1.0, 0.0, 0.0], top_k=3, min_score=0.0)
        h2 = reloaded.search([1.0, 0.0, 0.0], top_k=3, min_score=0.0)
        assert h1[0][0].text == h2[0][0].text
        assert abs(h1[0][1] - h2[0][1]) < 1e-6


def test_metrics_populated():
    with tempfile.TemporaryDirectory() as tmp:
        store = FaissVectorStore(index_dir=Path(tmp) / "idx")
        store.add(
            DocumentChunk(
                text="test",
                embedding=[1.0, 0.0, 0.0],
            )
        )

        class FakeEmbedder:
            last_cache_hit = True

            def embed_query(self, _):
                return [1.0, 0.0, 0.0]

        retriever = Retriever(
            store=store,
            embedder=FakeEmbedder(),
            semantic_cache=None,
            min_score=0.0,
        )
        retriever.retrieve("test query")
        m = retriever.last_metrics
        assert m.hits_count >= 1
        assert "total_rag_latency_ms" in m.to_dict()


if __name__ == "__main__":
    test_rag_query_context_active()
    test_retrieve_no_pdf_read_at_query_time()
    test_semantic_cache_hit()
    test_semantic_cache_exact_hash()
    test_light_rerank_boosts_discipline()
    test_metadata_content_type_filter()
    test_multi_index_single_embed()
    test_retrieval_performance_under_limit()
    test_faiss_consistent_results()
    test_metrics_populated()
    print("OK — test_rag_performance")
