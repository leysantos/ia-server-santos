from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk

VectorStore = FaissVectorStore

__all__ = ["DocumentChunk", "VectorStore", "FaissVectorStore"]
