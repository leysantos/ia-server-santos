"""
Domain Classifier — separa engenharia (NBR), orçamento (SINAPI/TCPO) e documentos internos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.knowledge.disciplines import SLUG_TO_DISCIPLINE
from core.knowledge.rag.agent_router import route_query_to_agent

KNOWLEDGE_ENGINEERING = "engineering"
KNOWLEDGE_COST = "cost"
KNOWLEDGE_DOCUMENTATION = "documentation"


class KnowledgeDomain(str, Enum):
    ENGINEERING = KNOWLEDGE_ENGINEERING
    COST = KNOWLEDGE_COST
    DOCUMENTATION = KNOWLEDGE_DOCUMENTATION
    MIXED = "mixed"


_COST_MARKERS = (
    "sinapi", "tcpo", "sicro", "orçamento", "orcamento", "custo unitário",
    "custo unitario", "composição de preço", "composicao de preco", "bdi",
    "planilha orçamentária", "planilha orcamentaria", "quantitativo de custo",
    "preço unitário", "preco unitario", "insumo", "insumos",
)

_ENGINEERING_MARKERS = (
    "dimensionar", "dimensionamento", "nbr ", "nbr-", "norma", "abnt",
    "viga", "laje", "pilar", "concreto", "armadura", "fundação", "fundacao",
    "carga elétrica", "carga eletrica", "esgoto", "hidráulic", "hidraulic",
    "5410", "6118", "5626", "8681",
)

_DOC_MARKERS = (
    "tdr", "termo de referência", "termo de referencia", "memorial descritivo",
    "projeto executivo", "planta baixa", "catálogo", "catalogo",
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _score_markers(text: str, markers: tuple[str, ...]) -> float:
    return sum(1.0 for m in markers if m in text)


@dataclass
class DomainClassification:
    query: str
    primary_domain: KnowledgeDomain
    agent_slug: str
    discipline: str
    knowledge_types: list[str] = field(default_factory=list)
    confidence: float = 0.0
    is_cost_query: bool = False
    is_engineering_query: bool = False
    is_documentation_query: bool = False

    def to_dict(self) -> dict:
        return {
            "primary_domain": self.primary_domain.value,
            "agent_slug": self.agent_slug,
            "discipline": self.discipline,
            "knowledge_types": self.knowledge_types,
            "confidence": round(self.confidence, 3),
            "is_cost_query": self.is_cost_query,
            "is_engineering_query": self.is_engineering_query,
            "is_documentation_query": self.is_documentation_query,
        }


def classify_domain(
    query: str,
    discipline_hint: Optional[str] = None,
) -> DomainClassification:
    """
    Classifica domínio técnico e tipo de conhecimento.

    Regra crítica: SINAPI/TCPO → COST only; NBR → ENGINEERING only.
    """
    normalized = _normalize(query)
    agent_slug = route_query_to_agent(query, discipline_hint=discipline_hint)

    disc_upper = (discipline_hint or "").strip().upper()
    if not disc_upper and agent_slug != "chat":
        from core.knowledge.disciplines import SLUG_TO_DISCIPLINE

        disc_upper = SLUG_TO_DISCIPLINE.get(agent_slug, "GERAL")

    cost_score = _score_markers(normalized, _COST_MARKERS)
    eng_score = _score_markers(normalized, _ENGINEERING_MARKERS)
    doc_score = _score_markers(normalized, _DOC_MARKERS)

    if re.search(r"nbr\s*\d|nbr-\d", normalized):
        eng_score += 2.0
    if "sinapi" in normalized:
        cost_score += 3.0
    if "tcpo" in normalized:
        cost_score += 2.5

    if disc_upper == "ORÇAMENTO":
        cost_score += 2.0
    elif disc_upper and disc_upper != "CHAT":
        eng_score += 1.0

    is_cost = cost_score >= 1.0 and cost_score >= eng_score
    is_eng = eng_score >= 1.0 and eng_score > cost_score
    is_doc = doc_score >= 1.0 and doc_score >= cost_score and doc_score >= eng_score

    if is_cost and is_eng:
        primary = KnowledgeDomain.MIXED
        knowledge_types = [KNOWLEDGE_ENGINEERING, KNOWLEDGE_COST]
        confidence = min(cost_score, eng_score) / max(cost_score, eng_score, 1)
    elif is_cost:
        primary = KnowledgeDomain.COST
        knowledge_types = [KNOWLEDGE_COST]
        confidence = cost_score / (cost_score + 0.1)
        agent_slug = "orcamento"
        disc_upper = "ORÇAMENTO"
    elif is_doc and not is_eng:
        primary = KnowledgeDomain.DOCUMENTATION
        knowledge_types = [KNOWLEDGE_DOCUMENTATION]
        confidence = doc_score / (doc_score + 0.1)
    elif is_eng or agent_slug not in ("chat", "orcamento"):
        primary = KnowledgeDomain.ENGINEERING
        knowledge_types = [KNOWLEDGE_ENGINEERING]
        confidence = eng_score / (eng_score + 0.1)
        if agent_slug == "orcamento" and not is_cost:
            agent_slug = route_query_to_agent(query, discipline_hint="ESTRUTURAL")
            disc_upper = "ESTRUTURAL"
    else:
        primary = KnowledgeDomain.MIXED
        knowledge_types = [KNOWLEDGE_ENGINEERING]
        confidence = 0.5

    return DomainClassification(
        query=query,
        primary_domain=primary,
        agent_slug=agent_slug,
        discipline=disc_upper or "GERAL",
        knowledge_types=knowledge_types,
        confidence=confidence,
        is_cost_query=is_cost,
        is_engineering_query=is_eng,
        is_documentation_query=is_doc,
    )
