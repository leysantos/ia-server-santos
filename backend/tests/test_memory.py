"""Testes do pipeline RAG v2 (sem dependência de Ollama em runtime)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile

from memory.chunker import estimate_tokens, split_text
from memory.embedding_cache import EmbeddingCache
from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk
from memory.retriever import Retriever


def test_split_text_dynamic():
    paragraph = "palavra " * 700
    text = f"{paragraph}\n\n{paragraph}\n\n{paragraph}"
    chunks = split_text(text, min_tokens=600, max_tokens=1200)
    assert len(chunks) >= 2
    for chunk in chunks:
        tokens = estimate_tokens(chunk)
        assert tokens <= 1400


def test_faiss_hybrid_search():
    with tempfile.TemporaryDirectory() as tmp:
        index_dir = Path(tmp) / "faiss_index"
        store = FaissVectorStore(index_dir=index_dir)

        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.9, 0.1, 0.0]
        vec_c = [0.0, 1.0, 0.0]
        vec_q = [0.95, 0.05, 0.0]

        store.add(DocumentChunk(
            text="norma estrutural concreto",
            embedding=vec_a,
            discipline="ESTRUTURAL",
            doc_type="nbr",
            metadata={"nbr_code": "6118", "norma": "NBR 6118"},
        ))
        store.add(DocumentChunk(
            text="concreto armado fundação",
            embedding=vec_b,
            discipline="ESTRUTURAL",
            doc_type="nbr",
            metadata={"nbr_code": "6118"},
        ))
        store.add(DocumentChunk(
            text="instalações elétricas",
            embedding=vec_c,
            discipline="ELÉTRICA",
            doc_type="nbr",
        ))
        store.save()

        reloaded = FaissVectorStore(index_dir=index_dir)
        hits = reloaded.search(
            vec_q,
            top_k=2,
            discipline="ESTRUTURAL",
            doc_type="nbr",
            nbr_boost="6118",
        )

        assert len(hits) == 2
        assert hits[0][1] >= hits[1][1]
        assert all(hit[0].discipline == "ESTRUTURAL" for hit in hits)


def test_retriever_dedup_and_limit():
    with tempfile.TemporaryDirectory() as tmp:
        index_dir = Path(tmp) / "faiss_index"
        store = FaissVectorStore(index_dir=index_dir)

        for _ in range(3):
            store.add(DocumentChunk(
                text="texto duplicado sobre viga de concreto armado",
                embedding=[1.0, 0.0, 0.0],
                discipline="ESTRUTURAL",
                doc_type="nbr",
                source="NBR 6118",
            ))

        store.save()

        class FakeEmbedder:
            def embed_query(self, _query):
                return [1.0, 0.0, 0.0]

        retriever = Retriever(
            store=store, embedder=FakeEmbedder(), min_score=0.0, semantic_cache=None
        )
        context = retriever.build_context(
            query="viga",
            discipline="ESTRUTURAL",
            doc_type="nbr",
        )

        assert context.count("texto duplicado") == 1


def test_embedding_cache():
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "cache.db"
        cache = EmbeddingCache(cache_path=cache_path)

        cache.set("texto", "nomic-embed-text", "document", [0.1, 0.2])
        assert cache.get("texto", "nomic-embed-text", "document") == [0.1, 0.2]
        assert cache.count() == 1


def test_dispatcher_backward_compatible():
    from core.dispatcher import dispatch

    result = dispatch({"discipline": "ESTRUTURAL", "input": "dimensionar viga"})
    assert result["discipline"] == "ESTRUTURAL"
    assert "result" in result
    assert "rag" not in result.get("extra", {})


def test_dispatcher_with_context():
    from core.dispatcher import dispatch

    result = dispatch({
        "discipline": "ESTRUTURAL",
        "input": "dimensionar viga",
        "context": "NBR 6118: requisitos de armadura",
    })
    assert result["extra"]["rag"]["active"] is True
    assert "NBR 6118" in result["result"]


def test_nbr_catalog():
    from memory.nbr_catalog import infer_discipline, parse_nbr_code

    assert parse_nbr_code("NBR-6118.pdf") == "6118"
    assert parse_nbr_code("nbr_8160.pdf") == "8160"
    assert infer_discipline("6118") == "ESTRUTURAL"
    assert infer_discipline("5410") == "ELÉTRICA"


def test_vector_store_dedup_by_path():
    with tempfile.TemporaryDirectory() as tmp:
        index_dir = Path(tmp) / "faiss_index"
        store = FaissVectorStore(index_dir=index_dir)
        pdf_path = "/tmp/NBR-6118.pdf"

        store.add(DocumentChunk(
            text="chunk",
            embedding=[1.0, 0.0, 0.0],
            metadata={"path": pdf_path},
        ))
        assert store.is_indexed(pdf_path)
        assert store.remove_by_path(pdf_path) == 1
        assert not store.is_indexed(pdf_path)


if __name__ == "__main__":
    test_split_text_dynamic()
    test_faiss_hybrid_search()
    test_retriever_dedup_and_limit()
    test_embedding_cache()
    test_dispatcher_backward_compatible()
    test_dispatcher_with_context()
    test_nbr_catalog()
    test_vector_store_dedup_by_path()
    print("OK: testes RAG v2 passaram")
