from pathlib import Path
from typing import Optional

from config.settings import FAISS_INDEX_DIR
from memory.embeddings import NomicEmbedder
from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk
from memory.pdf_indexer import PDFIndexer
from memory.retriever import Retriever


class RAGEngine:
    """
    Orquestrador RAG v2 para engenharia.

    Pipeline: embed (cache) → store (FAISS) → retrieve (hybrid search)
    """

    def __init__(
        self,
        index_dir: Path = FAISS_INDEX_DIR,
        embedder: Optional[NomicEmbedder] = None,
    ):
        self.embedder = embedder or NomicEmbedder()
        self.store = FaissVectorStore(index_dir=index_dir)
        self.retriever = Retriever(store=self.store, embedder=self.embedder)
        self.indexer = PDFIndexer(store=self.store, embedder=self.embedder)

    # --- EMBED ---

    def embed(self, text: str, task: str = "document") -> list[float]:
        if task == "query":
            return self.embedder.embed_query(text)
        return self.embedder.embed_document(text)

    def embed_batch(self, texts: list[str], task: str = "document") -> list[list[float]]:
        return self.embedder.embed_batch(texts, task=task)

    # --- STORE ---

    def store_text(
        self,
        text: str,
        source: str = "",
        doc_type: str = "",
        discipline: str = "",
        metadata: Optional[dict] = None,
    ) -> str:
        embedding = self.embed(text, task="document")
        chunk = DocumentChunk(
            text=text,
            embedding=embedding,
            source=source,
            doc_type=doc_type,
            discipline=discipline,
            metadata=metadata or {},
        )
        chunk_id = self.store.add(chunk)
        self.store.save()
        return chunk_id

    def store_chunks(self, chunks: list[DocumentChunk]) -> int:
        count = self.store.add_many(chunks)
        self.store.save()
        return count

    # --- RETRIEVE ---

    def retrieve(
        self,
        query: str,
        discipline: Optional[str] = None,
        doc_type: Optional[str] = None,
        nbr_code: Optional[str] = None,
        top_k: Optional[int] = None,
        agent_slug: Optional[str] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        return self.retriever.retrieve(
            query=query,
            discipline=discipline,
            doc_type=doc_type,
            nbr_code=nbr_code,
            top_k=top_k,
            agent_slug=agent_slug,
        )

    def build_context(
        self,
        query: str,
        discipline: Optional[str] = None,
        doc_type: Optional[str] = None,
        nbr_code: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> str:
        return self.retriever.build_context(
            query=query,
            discipline=discipline,
            doc_type=doc_type,
            nbr_code=nbr_code,
            top_k=top_k,
        )

    # --- PDF INDEXING ---

    def index_pdf(
        self,
        pdf_path: Path,
        doc_type: str = "nbr",
        discipline: str = "",
        force: bool = False,
    ) -> int:
        count = self.indexer.index_pdf(
            pdf_path=pdf_path,
            doc_type=doc_type,
            discipline=discipline,
            force=force,
        )
        self.store.save()
        return count

    def index_nbrs(self, discipline: str = "", force: bool = False) -> dict:
        return self.indexer.index_nbrs(discipline=discipline, force=force)

    def index_tdrs(self, discipline: str = "", force: bool = False) -> dict:
        return self.indexer.index_tdrs(discipline=discipline, force=force)

    def retrieve_context(
        self,
        query: str,
        domain: Optional[str] = None,
        discipline: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> str:
        """
        Recupera contexto técnico — multi-index (Knowledge Layer) ou índice legado.
        """
        from config import settings

        if settings.USE_KNOWLEDGE_ROUTER:
            from core.knowledge.knowledge_base_router import get_knowledge_router

            kc = get_knowledge_router().retrieve_context(
                query=query,
                domain=domain,
                discipline=discipline,
                top_k=top_k,
            )
            return kc.context_text

        return self.build_context(
            query=query,
            discipline=discipline,
            doc_type="nbr",
            top_k=top_k,
        )

    def enrich_route_result(self, route_result: dict) -> dict:
        """
        Enriquece o resultado do router com contexto RAG deduplicado.
        Compatível com o dispatcher existente.
        """
        from config import settings

        query = route_result.get("input", "")
        discipline = route_result.get("discipline")

        if not query or discipline in ("CHAT", "GERAL", None):
            return route_result

        if route_result.get("_use_rag") is False:
            return route_result

        if settings.USE_AGENT_SCOPED_RAG:
            from core.knowledge.rag.agent_retriever import retrieve_context_for_route

            result = retrieve_context_for_route(query, discipline=discipline)
            if result.context_text:
                route_result = dict(route_result)
                route_result["context"] = result.context_text
                route_result["agent_rag"] = result.to_dict()

        elif settings.USE_KNOWLEDGE_ROUTER:
            from core.knowledge.knowledge_base_router import enrich_route_with_knowledge

            route_result = enrich_route_with_knowledge(route_result)
        else:
            context = self.build_context(
                query=query,
                discipline=discipline,
                doc_type="nbr",
            )
            if context:
                route_result = dict(route_result)
                route_result["context"] = context

        if route_result.get("_project_id"):
            from core.project_rag.project_rag import augment_route_with_project_context

            route_result = augment_route_with_project_context(route_result)

        return route_result

    @property
    def indexed_chunks(self) -> int:
        return self.store.count()


def get_rag_engine() -> RAGEngine:
    """Factory singleton simples para uso no pipeline da aplicação."""
    if not hasattr(get_rag_engine, "_instance"):
        get_rag_engine._instance = RAGEngine()
    return get_rag_engine._instance
