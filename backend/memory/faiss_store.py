import json
from pathlib import Path
from typing import Optional

import faiss
import numpy as np

from config.settings import (
    FAISS_INDEX_DIR,
    RAG_BOOST_DISCIPLINE,
    RAG_BOOST_DOC_TYPE,
    RAG_BOOST_NBR,
    RAG_SEARCH_OVERSAMPLE,
)
from memory.models import DocumentChunk


class FaissVectorStore:
    """
    Vector store persistente com FAISS (IndexFlatIP + L2-normalized = cosine).
    Metadados em chunks.json; vetores em index.faiss.
    """

    META_FILE = "chunks.json"
    INDEX_FILE = "index.faiss"

    def __init__(self, index_dir: Path = FAISS_INDEX_DIR):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.index_dir / self.META_FILE
        self.index_path = self.index_dir / self.INDEX_FILE
        self.chunks: list[DocumentChunk] = []
        self.index: Optional[faiss.IndexFlatIP] = None
        self._dim: Optional[int] = None
        self._load()

    def _load(self):
        if not self.meta_path.exists():
            return

        with open(self.meta_path, encoding="utf-8") as f:
            data = json.load(f)

        self.chunks = [DocumentChunk.from_dict(item) for item in data.get("chunks", [])]

        if self.index_path.exists() and self.chunks:
            self.index = faiss.read_index(str(self.index_path))
            self._dim = self.index.d

    def reload(self) -> None:
        """Recarrega chunks e índice do disco (após indexação externa ou em background)."""
        self.chunks = []
        self.index = None
        self._dim = None
        self._load()

    def _rebuild_index(self):
        embeddings = [chunk.embedding for chunk in self.chunks if chunk.embedding]
        if not embeddings:
            self.index = None
            self._dim = None
            return

        matrix = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(matrix)
        self._dim = matrix.shape[1]
        self.index = faiss.IndexFlatIP(self._dim)
        self.index.add(matrix)

    def save(self):
        self.index_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": 2,
            "engine": "faiss",
            "count": len(self.chunks),
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }

        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        if self.index is not None:
            faiss.write_index(self.index, str(self.index_path))

    def add(self, chunk: DocumentChunk) -> str:
        if chunk.embedding:
            self._add_embedding(chunk.embedding)
        self.chunks.append(chunk)
        return chunk.id

    def add_many(self, chunks: list[DocumentChunk]) -> int:
        for chunk in chunks:
            self.add(chunk)
        return len(chunks)

    def _add_embedding(self, embedding: list[float]):
        vector = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(vector)

        if self.index is None:
            self._dim = vector.shape[1]
            self.index = faiss.IndexFlatIP(self._dim)

        self.index.add(vector)

    @staticmethod
    def _metadata_match(
        chunk: DocumentChunk,
        discipline: Optional[str],
        doc_type: Optional[str],
        nbr_code: Optional[str],
        content_type: Optional[str] = None,
    ) -> bool:
        if discipline and chunk.discipline and chunk.discipline.upper() != discipline.upper():
            return False
        if doc_type and chunk.doc_type and chunk.doc_type.lower() != doc_type.lower():
            return False
        if content_type:
            meta_ct = (chunk.metadata or {}).get("content_type", "").lower()
            if meta_ct and meta_ct != content_type.lower():
                return False
        if nbr_code and chunk.metadata.get("nbr_code") != nbr_code:
            return False
        return True

    @staticmethod
    def _rank_score(
        base_score: float,
        chunk: DocumentChunk,
        discipline: Optional[str],
        doc_type: Optional[str],
        nbr_code: Optional[str],
    ) -> float:
        score = float(base_score)
        if discipline and chunk.discipline == discipline:
            score += RAG_BOOST_DISCIPLINE
        elif discipline and chunk.discipline.upper() == discipline.upper():
            score += RAG_BOOST_DISCIPLINE
        if doc_type and chunk.doc_type == doc_type:
            score += RAG_BOOST_DOC_TYPE
        if nbr_code and chunk.metadata.get("nbr_code") == nbr_code:
            score += RAG_BOOST_NBR
        return score

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        discipline: Optional[str] = None,
        doc_type: Optional[str] = None,
        nbr_code: Optional[str] = None,
        nbr_boost: Optional[str] = None,
        min_score: float = 0.0,
        content_type: Optional[str] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        if not self.index or self.index.ntotal == 0:
            return []

        query_vec = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_vec)

        oversample = min(self.index.ntotal, max(top_k * RAG_SEARCH_OVERSAMPLE, top_k))
        scores, indices = self.index.search(query_vec, oversample)

        ranked: list[tuple[DocumentChunk, float]] = []
        boost_nbr = nbr_boost or nbr_code

        for base_score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue

            chunk = self.chunks[idx]
            if not self._metadata_match(
                chunk, discipline, doc_type, nbr_code, content_type
            ):
                continue

            final_score = self._rank_score(
                base_score, chunk, discipline, doc_type, boost_nbr
            )
            if final_score >= min_score:
                ranked.append((chunk, final_score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:top_k]

    def count(self) -> int:
        return len(self.chunks)

    def is_indexed(self, pdf_path: str) -> bool:
        return any(chunk.metadata.get("path") == pdf_path for chunk in self.chunks)

    def is_indexed_by_hash(self, content_hash: str) -> bool:
        return any(
            chunk.metadata.get("content_hash") == content_hash for chunk in self.chunks
        )

    def remove_by_path(self, pdf_path: str) -> int:
        before = len(self.chunks)
        self.chunks = [
            chunk for chunk in self.chunks
            if chunk.metadata.get("path") != pdf_path
        ]
        removed = before - len(self.chunks)
        if removed:
            self._rebuild_index()
        return removed

    def clear(self):
        self.chunks = []
        self.index = None
        self._dim = None
