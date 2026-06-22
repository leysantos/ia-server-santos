"""
Extração de texto de PDFs para indexação FAISS.

Ordem: pypdf → PyMuPDF → OCR (Tesseract via PyMuPDF, se disponível).
"""

from __future__ import annotations

import logging
import shutil
import warnings
from pathlib import Path

logger = logging.getLogger(__name__)

_MIN_PAGE_CHARS = 20
_OCR_DPI = 200


def extract_pdf_pages(pdf_path: Path, *, use_ocr: bool = True) -> list[tuple[int, str]]:
    """Retorna [(num_página, texto), ...] com texto não vazio."""
    pdf_path = Path(pdf_path).resolve()
    pages = _extract_pypdf(pdf_path)
    if not pages:
        pages = _extract_pymupdf(pdf_path)
    if not pages and use_ocr:
        pages = _extract_pymupdf_ocr(pdf_path)
    return pages


def _extract_pypdf(pdf_path: Path) -> list[tuple[int, str]]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Multiple definitions in dictionary",
                category=UserWarning,
            )
            reader = PdfReader(str(pdf_path))
    except Exception as exc:
        logger.debug("pypdf open falhou %s: %s", pdf_path.name, exc)
        return []

    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        if len(text) >= _MIN_PAGE_CHARS:
            pages.append((index, text))
    return pages


def _extract_pymupdf(pdf_path: Path) -> list[tuple[int, str]]:
    try:
        import fitz
    except ImportError:
        return []

    pages: list[tuple[int, str]] = []
    try:
        doc = fitz.open(pdf_path)
        try:
            for index in range(len(doc)):
                text = (doc[index].get_text("text") or "").strip()
                if len(text) >= _MIN_PAGE_CHARS:
                    pages.append((index + 1, text))
        finally:
            doc.close()
    except Exception as exc:
        logger.debug("PyMuPDF falhou %s: %s", pdf_path.name, exc)
    return pages


def _extract_pymupdf_ocr(pdf_path: Path) -> list[tuple[int, str]]:
    if not shutil.which("tesseract"):
        logger.debug("Tesseract ausente — OCR ignorado para %s", pdf_path.name)
        return []

    try:
        import fitz
    except ImportError:
        return []

    pages: list[tuple[int, str]] = []
    try:
        doc = fitz.open(pdf_path)
        try:
            for index in range(len(doc)):
                page = doc[index]
                try:
                    tp = page.get_textpage_ocr(dpi=_OCR_DPI, full=True)
                    text = (page.get_text(textpage=tp) or "").strip()
                except Exception as exc:
                    logger.debug("OCR página %s/%s: %s", index + 1, pdf_path.name, exc)
                    text = ""
                if len(text) >= _MIN_PAGE_CHARS:
                    pages.append((index + 1, text))
        finally:
            doc.close()
    except Exception as exc:
        logger.warning("OCR falhou %s: %s", pdf_path.name, exc)
    return pages
