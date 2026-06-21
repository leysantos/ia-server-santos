"""
Classificação automática de PDFs NBR/NR para importação em lote.

Pipeline (do mais rápido ao mais lento):
1. Nome do arquivo → código NBR/NR + catálogo
2. Primeira página do PDF → regex NBR/NR
3. (Opcional) LLM leve só para arquivos ambíguos
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from core.knowledge.disciplines import slug_for_discipline
from core.knowledge.ingestion import ClassificationResult
from core.knowledge.norm_bulk.nr_catalog import (
    infer_nr_discipline,
    nr_label,
    parse_nr_code,
)
from memory.nbr_catalog import infer_discipline, nbr_label, parse_nbr_code
from core.knowledge.norm_bulk.title_extract import extract_norm_display_name

logger = logging.getLogger(__name__)

_NORM_TITLE_HINT = re.compile(
    r"(?:NBR[\s\-_]?\d{4,5}|NR[\s\-_]?\d{1,2}|norma[\s\-_]?regulamentadora)",
    re.IGNORECASE,
)

_VALID_DISCIPLINES = (
    "ARQUITETURA",
    "ESTRUTURAL",
    "HIDROSSANITÁRIO",
    "DRENAGEM",
    "ELÉTRICA",
    "TELECOM",
    "INCÊNDIO",
    "GEOTECNIA",
    "TRANSPORTES",
    "SANEAMENTO",
    "TOPOGRAFIA",
    "DOCUMENTACAO",
    "SEGURANCA",
    "GERAL",
    "ORÇAMENTO",
    "MEIO AMBIENTE",
)


def _apply_display_name(
    path: Path,
    result: ClassificationResult,
    *,
    norm_kind: str,
    norm_code: str | None,
    snippet: str = "",
) -> ClassificationResult:
    display = extract_norm_display_name(
        path,
        norm_kind=norm_kind,
        norm_code=norm_code,
        first_page_text=snippet or None,
    )
    if display:
        result.metadata["norm_display_name"] = display
        result.metadata["norm_label"] = display
        if " - " in display:
            result.metadata["norm_title"] = display.split(" - ", 1)[1].strip()
    elif norm_kind == "NBR" and norm_code:
        result.metadata.setdefault("norm_label", nbr_label(norm_code))
    return result


def _result_from_nbr(
    path: Path,
    nbr: str,
    *,
    source: str,
    confidence: float,
    snippet: str = "",
) -> ClassificationResult:
    disc = infer_discipline(nbr) or "GERAL"
    slug = slug_for_discipline(disc)
    result = ClassificationResult(
        discipline_slug=slug,
        content_type="nbrs",
        confidence=confidence,
        source=source,
        mapped_discipline=disc,
        metadata={
            "nbr": nbr,
            "norm_kind": "NBR",
            "norm_code": nbr,
            "norm_label": nbr_label(nbr),
            "filename": path.name,
        },
    )
    return _apply_display_name(path, result, norm_kind="NBR", norm_code=nbr, snippet=snippet)


def _result_from_nr(
    path: Path,
    nr: str,
    *,
    source: str,
    confidence: float,
    snippet: str = "",
) -> ClassificationResult:
    disc = infer_nr_discipline(nr)
    slug = slug_for_discipline(disc)
    result = ClassificationResult(
        discipline_slug=slug,
        content_type="nbrs",
        confidence=confidence,
        source=source,
        mapped_discipline=disc,
        metadata={
            "nr": nr,
            "norm_kind": "NR",
            "norm_code": nr,
            "norm_label": nr_label(nr),
            "filename": path.name,
        },
    )
    return _apply_display_name(path, result, norm_kind="NR", norm_code=nr, snippet=snippet)


def _extract_first_page_text(path: Path, max_chars: int = 4000) -> str:
    if path.suffix.lower() != ".pdf":
        return ""
    try:
        from memory.pdf_indexer import PDFIndexer

        pages = PDFIndexer.extract_text(path)
        if not pages:
            return ""
        return (pages[0][1] or "")[:max_chars]
    except Exception as exc:
        logger.debug("Falha ao extrair 1ª página de %s: %s", path.name, exc)
        return ""


def _classify_with_llm(path: Path, snippet: str) -> Optional[ClassificationResult]:
    try:
        from config.settings import get_settings
        from models.ollama_client import OllamaClient

        settings = get_settings()
        client = OllamaClient(
            primary_model=settings.ollama_chat_light_model,
            timeout=45,
        )
        prompt = (
            "Classifique este PDF de norma técnica brasileira (NBR ou NR).\n"
            f"Arquivo: {path.name}\n"
            f"Trecho:\n{snippet[:2500]}\n\n"
            "Responda JSON com: norm_kind (NBR ou NR), norm_code (só dígitos), "
            "discipline (uma de: "
            + ", ".join(_VALID_DISCIPLINES)
            + ")."
        )
        raw, _model = client.generate(prompt, format_json=True, options={"num_predict": 120})
        data = json.loads(raw)
        kind = str(data.get("norm_kind") or "").upper()
        code = re.sub(r"\D", "", str(data.get("norm_code") or ""))
        disc = str(data.get("discipline") or "GERAL").upper()
        if disc not in _VALID_DISCIPLINES:
            disc = "GERAL"
        if kind == "NBR" and code:
            return _result_from_nbr(path, code, source="llm_fallback", confidence=0.72)
        if kind == "NR" and code:
            return _result_from_nr(path, code.lstrip("0") or "0", source="llm_fallback", confidence=0.72)
        slug = slug_for_discipline(disc)
        return ClassificationResult(
            discipline_slug=slug,
            content_type="nbrs",
            confidence=0.68,
            source="llm_fallback",
            mapped_discipline=disc,
            metadata={"filename": path.name, "norm_kind": kind or "UNKNOWN"},
        )
    except Exception as exc:
        logger.warning("LLM classify falhou para %s: %s", path.name, exc)
        return None


def classify_norm_pdf(
    path: Path,
    *,
    use_ai_fallback: bool = False,
    mark_edition_outdated: bool = False,
) -> ClassificationResult:
    """Classifica PDF de norma (NBR/NR) para ingestão em lote."""
    path = path.resolve()
    name = path.name

    nbr = parse_nbr_code(name)
    snippet = ""
    if nbr:
        result = _result_from_nbr(path, nbr, source="nbr_filename", confidence=0.94)
    else:
        nr = parse_nr_code(name)
        if nr:
            result = _result_from_nr(path, nr, source="nr_filename", confidence=0.92)
        else:
            snippet = _extract_first_page_text(path)
            nbr = parse_nbr_code(snippet) if snippet else None
            if nbr:
                result = _result_from_nbr(
                    path, nbr, source="nbr_pdf_text", confidence=0.86, snippet=snippet
                )
            else:
                nr = parse_nr_code(snippet) if snippet else None
                if nr:
                    result = _result_from_nr(
                        path, nr, source="nr_pdf_text", confidence=0.84, snippet=snippet
                    )
                elif use_ai_fallback and snippet and _NORM_TITLE_HINT.search(snippet):
                    llm_result = _classify_with_llm(path, snippet)
                    if llm_result:
                        result = llm_result
                    else:
                        result = ClassificationResult(
                            discipline_slug="geral",
                            content_type="nbrs",
                            confidence=0.45,
                            source="unknown_norm",
                            mapped_discipline="GERAL",
                            metadata={"filename": name},
                        )
                else:
                    result = ClassificationResult(
                        discipline_slug="geral",
                        content_type="nbrs",
                        confidence=0.50 if _NORM_TITLE_HINT.search(name) else 0.40,
                        source="filename_heuristic",
                        mapped_discipline="GERAL",
                        metadata={"filename": name},
                    )
                    result = _apply_display_name(
                        path, result, norm_kind="UNKNOWN", norm_code=None, snippet=snippet
                    )

    if mark_edition_outdated:
        result.metadata["edition_outdated"] = True
        result.metadata["edition_note"] = (
            "Acervo histórico — verificar vigência antes de citar em entrega formal."
        )

    return result
