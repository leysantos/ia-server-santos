import json
import logging
import os
import shutil
import threading
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
from memory.nbr_catalog import nbr_codes_match, normalize_nbr_code

logger = logging.getLogger(__name__)


class FaissVectorStore:
    """
    Vector store persistente com FAISS (IndexFlatIP + L2-normalized = cosine).
    Metadados em chunks.json; vetores em index.faiss.
    """

    META_FILE = "chunks.json"
    INDEX_FILE = "index.faiss"
    META_BACKUP_SUFFIX = ".json.bak"
    META_TEMP_SUFFIX = ".json.tmp"
    INDEX_TEMP_SUFFIX = ".faiss.tmp"

    def __init__(self, index_dir: Path = FAISS_INDEX_DIR):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.index_dir / self.META_FILE
        self.index_path = self.index_dir / self.INDEX_FILE
        self._meta_backup_path = self.meta_path.with_suffix(self.META_BACKUP_SUFFIX)
        self._meta_temp_path = self.meta_path.with_suffix(self.META_TEMP_SUFFIX)
        self._index_temp_path = self.index_path.with_suffix(self.INDEX_TEMP_SUFFIX)
        self.chunks: list[DocumentChunk] = []
        self.index: Optional[faiss.IndexFlatIP] = None
        self._dim: Optional[int] = None
        self._io_lock = threading.RLock()
        self._loaded_mtime: float = 0.0
        self._load()

    def _read_meta_payload(self) -> dict:
        candidates = (self.meta_path, self._meta_backup_path)
        last_error: Exception | None = None

        for path in candidates:
            if not path.exists():
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if path != self.meta_path:
                    logger.warning(
                        "Recuperado %s a partir do backup %s",
                        self.meta_path.name,
                        path.name,
                    )
                return data if isinstance(data, dict) else {"chunks": []}
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.warning("JSON inválido em %s: %s", path, exc)
            except OSError as exc:
                last_error = exc
                logger.warning("Falha ao ler %s: %s", path, exc)

        if last_error is not None:
            logger.error(
                "Não foi possível carregar metadados FAISS em %s (%s)",
                self.index_dir,
                last_error,
            )
        return {"chunks": []}

    def _load(self):
        with self._io_lock:
            if not self.meta_path.exists() and not self._meta_backup_path.exists():
                self.chunks = []
                self.index = None
                self._dim = None
                self._loaded_mtime = 0.0
                return

            data = self._read_meta_payload()
            self.chunks = [DocumentChunk.from_dict(item) for item in data.get("chunks", [])]

            if self.index_path.exists() and self.chunks:
                try:
                    self.index = faiss.read_index(str(self.index_path))
                    self._dim = self.index.d
                except Exception as exc:
                    logger.warning(
                        "Falha ao carregar %s — reconstruindo a partir dos embeddings (%s)",
                        self.index_path.name,
                        exc,
                    )
                    self._rebuild_index()
            else:
                self.index = None
                self._dim = None

            if self.meta_path.exists():
                self._loaded_mtime = self.meta_path.stat().st_mtime
            elif self._meta_backup_path.exists():
                self._loaded_mtime = self._meta_backup_path.stat().st_mtime

    def reload(self) -> None:
        """Recarrega chunks e índice do disco (após indexação externa ou em background)."""
        with self._io_lock:
            previous_chunks = list(self.chunks)
            self.chunks = []
            self.index = None
            self._dim = None
            self._load()
            if not self.chunks and previous_chunks:
                logger.warning(
                    "Reload em %s retornou vazio — mantendo estado em memória (%d chunks)",
                    self.index_dir.name,
                    len(previous_chunks),
                )
                self.chunks = previous_chunks
                self._rebuild_index()

    def reload_if_changed(self) -> bool:
        """Recarrega somente se chunks.json mudou no disco."""
        if not self.meta_path.exists():
            return False
        mtime = self.meta_path.stat().st_mtime
        if mtime <= self._loaded_mtime:
            return False
        self.reload()
        return True

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

    def _atomic_write_meta(self, payload: dict) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        with open(self._meta_temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())

        if self.meta_path.exists():
            try:
                shutil.copy2(self.meta_path, self._meta_backup_path)
            except OSError as exc:
                logger.debug("Backup chunks.json ignorado: %s", exc)

        os.replace(self._meta_temp_path, self.meta_path)
        self._loaded_mtime = self.meta_path.stat().st_mtime

    def _atomic_write_index(self) -> None:
        if self.index is None:
            if self.index_path.exists():
                self.index_path.unlink(missing_ok=True)
            return

        faiss.write_index(self.index, str(self._index_temp_path))
        os.replace(self._index_temp_path, self.index_path)

    def save(self):
        with self._io_lock:
            payload = {
                "version": 2,
                "engine": "faiss",
                "count": len(self.chunks),
                "chunks": [chunk.to_dict() for chunk in self.chunks],
            }
            self._atomic_write_meta(payload)
            self._atomic_write_index()

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
        if nbr_code and not nbr_codes_match(chunk.metadata.get("nbr_code"), nbr_code):
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
        if nbr_code and nbr_codes_match(chunk.metadata.get("nbr_code"), nbr_code):
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
        boost_nbr = normalize_nbr_code(nbr_boost or nbr_code)

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
            self.save()
        return removed

    def remove_where(self, predicate) -> int:
        """Remove chunks cujo metadata satisfaz predicate(metadata) -> bool."""
        before = len(self.chunks)
        self.chunks = [
            chunk for chunk in self.chunks
            if not predicate(chunk.metadata or {})
        ]
        removed = before - len(self.chunks)
        if removed:
            self._rebuild_index()
            self.save()
        return removed

    def clear(self):
        self.chunks = []
        self.index = None
        self._dim = None
        self.save()
