"""Classificação de arquivos do projeto — prancha vs documento técnico."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Memorial, parecer, termo, memória de cálculo, etc.
_DOCUMENT_KEYWORDS = (
    "memorial",
    "memoria",
    "memória",
    "memoria de calculo",
    "memória de cálculo",
    "memoria de calculo",
    "memoria de cálculo",
    "termo de",
    "termo ",
    "carta",
    "parecer",
    "resposta",
    "obs-",
    "obs_",
    "observacao",
    "observação",
    "checklist",
    "especificacao",
    "especificação",
    "relatorio",
    "relatório",
    "laudo",
    "orcamento",
    "orçamento",
    "planilha",
    "item-02-md",
    "item-03",
    "item-04",
    "item-05",
    "-md-",
    "_md_",
    " md ",
    "descritivo",
    "memorando",
    "declaracao",
    "declaração",
)

# Plantas, PPCI/ARQ com revisão, folhas técnicas
_PRANCHA_KEYWORDS = (
    "planta",
    "prancha",
    "folha",
    "layout",
    "corte",
    "fachada",
    "detalhe",
    "situação",
    "situacao",
    "locação",
    "locacao",
    "ppci_",
    "ppci-",
    "arq_",
    "arq-",
    "est_",
    "ele_",
    "hid_",
)

_REVISION_RE = re.compile(r"[\s_\-]?r(\d{2})\b", re.I)


def classify_project_file(filename: str, *, agent_key: str | None = None) -> dict[str, Any]:
    """
    Retorna tipo do arquivo para o workflow.

    tipos:
      - prancha: desenho/planta — pipeline completo (prancha PDF, revisão, entrega)
      - documento: memorial, parecer, termo, memória de cálculo — só indexação
      - cad: DWG/DXF
      - bim: IFC
    """
    name = Path(filename).name
    lower = name.lower()
    ext = Path(name).suffix.lower()

    if agent_key in ("dwg", "dxf") or ext in (".dwg", ".dxf"):
        return _result("cad", "desenho_cad", lower, confidence=0.95, agent_key="dwg")

    if agent_key == "ifc" or ext == ".ifc":
        return _result("bim", "modelo_bim", lower, confidence=0.95, agent_key="ifc")

    if ext != ".pdf" and agent_key != "pdf":
        return _result("outro", "nao_suportado", lower, confidence=0.5, pipeline="skip")

    doc_score = sum(1 for k in _DOCUMENT_KEYWORDS if k in lower)
    prancha_score = sum(1 for k in _PRANCHA_KEYWORDS if k in lower)

    # Prefixos típicos de prancha com revisão (ARQ_R02, PPCI_..._R02)
    if _REVISION_RE.search(lower) and any(p in lower for p in ("arq", "ppci", "est", "ele", "hid", "planta")):
        prancha_score += 2

    # MD explícito no nome = memorial descritivo
    if re.search(r"\bmd[_\-\s]|item-\d+-md", lower):
        doc_score += 3

    if "memoria" in lower or "memorial" in lower or "memória" in lower:
        doc_score += 2

    if "parecer" in lower or "carta" in lower or "termo" in lower:
        doc_score += 2

    if prancha_score > doc_score:
        subtipo = _infer_prancha_subtype(lower)
        return _result("prancha", subtipo, lower, confidence=0.7 + min(0.25, prancha_score * 0.05))

    if doc_score > 0:
        subtipo = _infer_document_subtype(lower)
        return _result("documento", subtipo, lower, confidence=0.75 + min(0.2, doc_score * 0.05))

    # PDF genérico sem pistas → documento (não gera prancha falsa)
    return _result("documento", "pdf_generico", lower, confidence=0.55)


def _infer_prancha_subtype(lower: str) -> str:
    if "ppci" in lower or "pci" in lower or "incendio" in lower:
        return "prancha_pci"
    if "arq" in lower or "planta" in lower or "fachada" in lower:
        return "prancha_arquitetura"
    if "est" in lower or "fund" in lower:
        return "prancha_estrutural"
    if "ele" in lower:
        return "prancha_eletrica"
    if "hid" in lower:
        return "prancha_hidraulica"
    return "prancha_tecnica"


def _infer_document_subtype(lower: str) -> str:
    if "memoria" in lower or "memorial" in lower or "memória" in lower:
        if "calculo" in lower or "cálculo" in lower:
            return "memoria_calculo"
        return "memorial"
    if "parecer" in lower:
        return "parecer"
    if "carta" in lower:
        return "carta"
    if "termo" in lower:
        return "termo"
    if "md" in lower:
        return "memorial_descritivo"
    return "documento_tecnico"


def _result(
    tipo: str,
    subtipo: str,
    filename: str,
    *,
    confidence: float,
    agent_key: str | None = None,
    pipeline: str | None = None,
) -> dict[str, Any]:
    if pipeline is None:
        pipeline = "full" if tipo in ("prancha", "cad", "bim") else "index"
    return {
        "tipo_arquivo": tipo,
        "subtipo": subtipo,
        "filename": filename,
        "confidence": round(confidence, 2),
        "pipeline": pipeline,
        "agent_key": agent_key or ("pdf" if tipo in ("prancha", "documento") else tipo),
        "is_prancha": tipo == "prancha",
        "is_documento": tipo == "documento",
    }
