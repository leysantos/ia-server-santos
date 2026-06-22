import logging
from pathlib import Path
from typing import Optional

from config.settings import NBR_DIR, TDR_DIR
from memory.chunker import split_text
from memory.embeddings import NomicEmbedder
from memory.nbr_catalog import infer_discipline, nbr_label, parse_nbr_code, normalize_nbr_code
from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk

logger = logging.getLogger(__name__)


class PDFIndexer:
    """
    Pipeline de indexação de PDFs (NBRs e TDRs).

    Requer pypdf instalado para extração de texto:
        pip install pypdf
    """

    DOC_TYPES = {
        "nbr": NBR_DIR,
        "tdr": TDR_DIR,
    }

    def __init__(
        self,
        store: FaissVectorStore,
        embedder: Optional[NomicEmbedder] = None,
    ):
        self.store = store
        self.embedder = embedder or NomicEmbedder()

    @staticmethod
    def extract_text(pdf_path: Path) -> list[tuple[int, str]]:
        from core.knowledge.pdf_text_extractor import extract_pdf_pages

        return extract_pdf_pages(pdf_path)

    def _resolve_nbr_metadata(
        self,
        pdf_path: Path,
        discipline: str,
        doc_type: str,
        content_hash: str = "",
    ) -> tuple[str, str, dict]:
        from core.knowledge.metadata import read_metadata
        from core.knowledge.norm_packs.legal import resolve_legal_source
        from memory.nbr_catalog import resolve_norm_code
        from memory.nbr_edition import parse_edition_year

        sidecar = read_metadata(pdf_path) or {}
        nbr_code = resolve_norm_code(pdf_path.name, sidecar)
        resolved_discipline = discipline or infer_discipline(
            nbr_code.split("-")[-1] if nbr_code and nbr_code.startswith("NR-") else nbr_code
        )
        label = nbr_label(nbr_code) if nbr_code and not nbr_code.startswith("NR-") else (nbr_code or pdf_path.stem)

        metadata: dict = {
            "path": str(pdf_path.resolve()),
            "filename": pdf_path.name,
            "content_hash": content_hash,
            "knowledge_base": "nbr",
        }
        legal = resolve_legal_source(sidecar, file_path=pdf_path, doc_type=doc_type)
        if legal.value != "missing":
            metadata["legal_source"] = legal.value
        if sidecar.get("content_type"):
            metadata["content_type"] = sidecar["content_type"]
        if sidecar.get("norm_kind"):
            metadata["norm_kind"] = sidecar["norm_kind"]
        if nbr_code:
            metadata["nbr_code"] = normalize_nbr_code(nbr_code)
            metadata["norm_code"] = metadata["nbr_code"]
            if nbr_code.startswith("NR-"):
                metadata["norma"] = nbr_code
            else:
                metadata["norma"] = nbr_label(nbr_code)
            edition_year = sidecar.get("edition_year") or parse_edition_year(pdf_path.name, nbr_code)
            if edition_year:
                metadata["edition_year"] = int(edition_year)

        return resolved_discipline, label, metadata

    def index_pdf(
        self,
        pdf_path: Path,
        doc_type: str = "nbr",
        discipline: str = "",
        source: Optional[str] = None,
        force: bool = False,
        pages: list[tuple[int, str]] | None = None,
    ) -> int:
        pdf_path = Path(pdf_path).resolve()
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

        pdf_key = str(pdf_path)
        if self.store.is_indexed(pdf_key) and not force:
            return 0

        from core.knowledge.resolver import file_content_hash

        content_hash = file_content_hash(pdf_path)
        if self.store.is_indexed_by_hash(content_hash) and not force:
            return 0

        if force and self.store.is_indexed(pdf_key):
            self.store.remove_by_path(pdf_key)

        pages = pages if pages is not None else self.extract_text(pdf_path)
        if not pages:
            raise ValueError(f"Nenhum texto extraído do PDF: {pdf_path.name}")

        resolved_discipline, label, metadata = self._resolve_nbr_metadata(
            pdf_path, discipline, doc_type, content_hash
        )
        source_name = source or label
        pending_chunks: list[tuple[int, str]] = []
        for page_num, page_text in pages:
            for chunk_text in split_text(page_text):
                pending_chunks.append((page_num, chunk_text))

        if not pending_chunks:
            raise ValueError(f"Nenhum chunk gerado do PDF: {pdf_path.name}")

        chunk_texts = [text for _, text in pending_chunks]
        embeddings = self.embedder.embed_batch_optional(chunk_texts, task="document")
        chunks_to_store: list[DocumentChunk] = []
        failed_chunks = 0

        for (page_num, chunk_text), embedding in zip(pending_chunks, embeddings):
            if embedding is None:
                failed_chunks += 1
                continue
            chunks_to_store.append(
                DocumentChunk(
                    text=chunk_text,
                    embedding=embedding,
                    source=source_name,
                    doc_type=doc_type,
                    discipline=resolved_discipline,
                    page=page_num,
                    metadata=dict(metadata),
                )
            )

        if failed_chunks:
            logger.warning(
                "%s: %d/%d chunks sem embedding (Ollama); indexação parcial",
                pdf_path.name,
                failed_chunks,
                len(pending_chunks),
            )

        if not chunks_to_store:
            raise RuntimeError(
                f"Nenhum chunk indexado para {pdf_path.name} — Ollama indisponível ou sobrecarregado"
            )

        return self.store.add_many(chunks_to_store)

    def index_directory(
        self,
        directory: Path,
        doc_type: str = "nbr",
        discipline: str = "",
        force: bool = False,
    ) -> dict:
        directory = Path(directory)
        summary = {
            "indexed_files": 0,
            "skipped_files": 0,
            "indexed_chunks": 0,
            "errors": [],
            "files": [],
        }

        pdfs = sorted(directory.glob("**/*.pdf"))
        if not pdfs:
            summary["errors"].append({
                "file": str(directory),
                "error": "Nenhum PDF encontrado no diretório",
            })
            return summary

        for pdf_path in pdfs:
            try:
                count = self.index_pdf(
                    pdf_path=pdf_path,
                    doc_type=doc_type,
                    discipline=discipline,
                    force=force,
                )
                if count == 0:
                    summary["skipped_files"] += 1
                    summary["files"].append({
                        "file": pdf_path.name,
                        "status": "skipped",
                        "chunks": 0,
                    })
                else:
                    summary["indexed_files"] += 1
                    summary["indexed_chunks"] += count
                    summary["files"].append({
                        "file": pdf_path.name,
                        "status": "indexed",
                        "chunks": count,
                    })
            except Exception as exc:
                summary["errors"].append({"file": str(pdf_path), "error": str(exc)})

        self.store.save()
        return summary

    def index_nbrs(self, discipline: str = "", force: bool = False) -> dict:
        NBR_DIR.mkdir(parents=True, exist_ok=True)
        return self.index_directory(
            NBR_DIR,
            doc_type="nbr",
            discipline=discipline,
            force=force,
        )

    def index_tdrs(self, discipline: str = "", force: bool = False) -> dict:
        TDR_DIR.mkdir(parents=True, exist_ok=True)
        return self.index_directory(
            TDR_DIR,
            doc_type="tdr",
            discipline=discipline,
            force=force,
        )
