"""Fontes legais permitidas na base normativa — produto comercializável."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional


class NormLegalSource(str, Enum):
    """Origem do documento na base — usado em carimbo, RAG e auditoria."""

    ABNT_LICENSED_PDF = "abnt_licensed_pdf"
    """PDF oficial adquirido/licenciado pelo cliente (upload manual)."""

    PUBLIC_LEGISLATION = "public_legislation"
    """Legislação pública: decretos, leis, ITs de órgãos públicos."""

    UNKNOWN = "unknown"
    """Origem não declarada — não elegível para citação no carimbo."""

    MISSING = "missing"
    """Norma exigida pelo pacote, sem PDF licenciado na base."""


STAMP_ELIGIBLE_SOURCES = frozenset({NormLegalSource.ABNT_LICENSED_PDF.value})

COMMERCIAL_LEGAL_NOTICE = (
    "Normas ABNT (NBR) são obras protegidas. Este sistema indexa apenas PDFs "
    "oficiais fornecidos pelo cliente sob licença válida, ou legislação pública. "
    "Não reproduzimos, reescrevemos nem distribuímos texto normativo via IA."
)

STAMP_LEGAL_FILTER_NOTICE = (
    "Carimbo cita somente NBRs indexadas a partir de PDF licenciado (ABNT/acervo do cliente)."
)

UPLOAD_INSTRUCTION = (
    "Adquira o PDF oficial na ABNT ou use o acervo licenciado do escritório. "
    "Em Configurações → Importações, faça upload do arquivo e marque como NBR."
)


def default_legal_source_for_content_type(content_type: str) -> NormLegalSource:
    ct = (content_type or "").lower()
    if ct in ("nbrs", "nbr"):
        return NormLegalSource.ABNT_LICENSED_PDF
    if ct == "regional":
        return NormLegalSource.PUBLIC_LEGISLATION
    return NormLegalSource.UNKNOWN


def resolve_legal_source(
    meta: Mapping[str, Any] | None,
    *,
    file_path: Path | str | None = None,
    doc_type: str | None = None,
) -> NormLegalSource:
    """Resolve origem legal a partir de metadados do chunk/sidecar/catálogo."""
    if meta:
        explicit = meta.get("legal_source")
        if explicit in {s.value for s in NormLegalSource}:
            return NormLegalSource(str(explicit))

    path = Path(file_path) if file_path else None
    sidecar_meta: dict[str, Any] | None = None
    if path and path.is_file():
        try:
            from core.knowledge.metadata import read_metadata

            sidecar_meta = read_metadata(path)
            if sidecar_meta and sidecar_meta.get("legal_source") in {s.value for s in NormLegalSource}:
                return NormLegalSource(str(sidecar_meta["legal_source"]))
        except Exception:
            pass

    content_type = ""
    if meta:
        content_type = str(meta.get("content_type") or "")
    if not content_type and sidecar_meta:
        content_type = str(sidecar_meta.get("content_type") or "")

    if content_type:
        resolved = default_legal_source_for_content_type(content_type)
        if resolved != NormLegalSource.UNKNOWN:
            return resolved

    if doc_type and doc_type.lower() == "nbr":
        return NormLegalSource.ABNT_LICENSED_PDF

    return NormLegalSource.UNKNOWN


def is_stamp_eligible(legal_source: str | NormLegalSource | None) -> bool:
    """Somente PDF ABNT licenciado pode aparecer no carimbo como NBR consultada."""
    if isinstance(legal_source, NormLegalSource):
        return legal_source.value in STAMP_ELIGIBLE_SOURCES
    return str(legal_source or "") in STAMP_ELIGIBLE_SOURCES


def legal_source_for_ingest(content_type: str) -> Optional[str]:
    """Valor `legal_source` gravado na ingestão de documentos."""
    src = default_legal_source_for_content_type(content_type)
    if src == NormLegalSource.UNKNOWN:
        return None
    return src.value
