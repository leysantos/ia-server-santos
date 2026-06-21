"""Importação em lote de NBRs/NRs com classificação automática."""

from core.knowledge.norm_bulk.classifier import classify_norm_pdf
from core.knowledge.norm_bulk.service import bulk_ingest_norm_pdfs

__all__ = ["classify_norm_pdf", "bulk_ingest_norm_pdfs"]
