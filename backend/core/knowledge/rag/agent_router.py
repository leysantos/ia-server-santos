"""
Agent Router — roteia query para o agente correto (backend/agents/*.py).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from core.knowledge.disciplines import slug_for_discipline
from core.knowledge.rag.agent_scopes import AGENT_SCOPES, AGENT_MODULES, DISCIPLINE_TO_AGENT_SLUG

_CHAT_MARKERS = (
    "olá", "ola", "oi", "bom dia", "boa tarde", "boa noite", "obrigado",
    "obrigada", "tudo bem", "como vai", "quem é você", "quem e voce",
    "me ajude", "conversar", "chat",
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def route_query_to_agent(
    query: str,
    discipline_hint: Optional[str] = None,
) -> str:
    """
    Retorna slug do agente (módulo agents/*.py sem .py).

    Prioridade:
      1. discipline_hint do dispatcher (/chat, /orchestrate)
      2. scoring por keywords/NBRs por agente
      3. chat (fallback conversacional)
    """
    if discipline_hint:
        disc = discipline_hint.strip().upper()
        if disc == "CHAT":
            return "chat"
        if disc in DISCIPLINE_TO_AGENT_SLUG:
            return DISCIPLINE_TO_AGENT_SLUG[disc]
        slug = slug_for_discipline(discipline_hint)
        if slug in AGENT_SCOPES:
            return slug

    normalized = _normalize(query)
    if not normalized.strip():
        return "chat"

    if any(m in normalized for m in _CHAT_MARKERS) and len(normalized.split()) < 12:
        if not re.search(r"nbr\s*\d|sinapi|tcpo|dimension", normalized):
            return "chat"

    scores: dict[str, float] = {}
    for agent in AGENT_MODULES:
        if agent == "chat":
            continue
        scope = AGENT_SCOPES[agent]
        score = 0.0
        for kw in scope.priority_keywords:
            if kw in normalized:
                score += 1.0
        for nbr in scope.priority_nbrs:
            pattern = nbr.replace(" ", r"\s*")
            if re.search(rf"nbr\s*{pattern}|nbr{nbr}|\b{nbr}\b", normalized):
                score += 3.0
        if score > 0:
            scores[agent] = score

    if not scores:
        return "chat"

    return max(scores, key=scores.get)


def agent_from_discipline(discipline: Optional[str]) -> str:
    """Atalho quando disciplina já foi resolvida pelo dispatcher."""
    return route_query_to_agent("", discipline_hint=discipline)
