"""
Análise de feedback do PostgreSQL — agrupamento e detecção de padrões.

Rule-based (sem LLM): identifica respostas ruins, erros recorrentes e temas frequentes.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from core.database.connection import is_db_enabled, session_scope
from core.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)

LOW_QUALITY_THRESHOLD = 2

PT_STOPWORDS = frozenset(
    """
    a o e de do da dos das em no na nos nas um uma uns unas para por com sem
    que se ou ao aos à às como mais menos muito pouco sobre entre até quando
    onde qual quais este esta estes estas esse essa esses essas isso aquilo
    meu minha seu sua nosso nossa eu tu ele ela nós vocês eles elas ser estar
    ter haver fazer dar ir vir preciso quero gostaria favor olá oi boa tarde
    noite dia preciso dimensionar calcular analisar verificar avaliar
    """.split()
)


@dataclass
class AgentFeedbackStats:
    agent_name: str
    discipline: str
    total_count: int = 0
    rated_count: int = 0
    low_quality_count: int = 0
    avg_rating: Optional[float] = None
    low_quality_items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DisciplineAnalysis:
    discipline: str
    agent_name: str
    feedback_sample_size: int
    low_quality_count: int
    common_errors: list[str]
    frequent_themes: list[str]
    error_patterns: dict[str, int]
    theme_counts: dict[str, int]
    avg_rating: Optional[float]
    agents: list[AgentFeedbackStats] = field(default_factory=list)


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip()


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    tokens = re.findall(r"[a-z0-9]{3,}", normalized)
    return [t for t in tokens if t not in PT_STOPWORDS]


def _extract_phrases(text: str, min_len: int = 12) -> list[str]:
    """Extrai frases curtas de feedback/correção para padrões de erro."""
    if not text:
        return []
    cleaned = text.strip()
    parts = re.split(r"[.!?\n;]+", cleaned)
    phrases = []
    for part in parts:
        phrase = part.strip()
        if len(phrase) >= min_len:
            phrases.append(phrase[:200])
    if not phrases and len(cleaned) >= min_len:
        phrases.append(cleaned[:200])
    return phrases


def _top_items(counter: Counter, limit: int = 5, min_count: int = 1) -> list[str]:
    return [item for item, count in counter.most_common(limit) if count >= min_count]


def analyze_rows(rows: list[Any]) -> dict[str, DisciplineAnalysis]:
    """Agrupa feedback por disciplina e extrai padrões."""
    by_discipline: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        discipline = (row.discipline or "GERAL").upper()
        by_discipline[discipline].append(row)

    results: dict[str, DisciplineAnalysis] = {}

    for discipline, items in by_discipline.items():
        error_counter: Counter = Counter()
        theme_counter: Counter = Counter()
        ratings: list[int] = []
        low_quality: list[dict[str, Any]] = []
        agents_stats: dict[str, AgentFeedbackStats] = {}

        for row in items:
            agent = row.agent_name or "unknown_agent"
            if agent not in agents_stats:
                agents_stats[agent] = AgentFeedbackStats(
                    agent_name=agent,
                    discipline=discipline,
                )
            stats = agents_stats[agent]
            stats.total_count += 1

            if row.rating is not None:
                stats.rated_count += 1
                ratings.append(row.rating)
                if row.rating <= LOW_QUALITY_THRESHOLD:
                    stats.low_quality_count += 1
                    item = DatabaseRepository.serialize_agent_feedback(row)
                    stats.low_quality_items.append(item)
                    low_quality.append(item)

            for phrase in _extract_phrases(row.feedback_text or ""):
                error_counter[_normalize_text(phrase)] += 1
            for phrase in _extract_phrases(row.corrected_answer or ""):
                error_counter[f"correcao: {_normalize_text(phrase)}"] += 1

            for token in _tokenize(row.input_text or ""):
                theme_counter[token] += 1
            bigrams = _tokenize(row.input_text or "")
            for i in range(len(bigrams) - 1):
                theme_counter[f"{bigrams[i]} {bigrams[i+1]}"] += 1

        primary_agent = max(agents_stats, key=lambda a: agents_stats[a].total_count) if agents_stats else ""
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        common_errors = _top_items(error_counter, limit=8, min_count=1)
        frequent_themes = _top_items(theme_counter, limit=10, min_count=2)

        results[discipline] = DisciplineAnalysis(
            discipline=discipline,
            agent_name=primary_agent,
            feedback_sample_size=len(items),
            low_quality_count=len(low_quality),
            common_errors=common_errors,
            frequent_themes=frequent_themes,
            error_patterns=dict(error_counter.most_common(20)),
            theme_counts=dict(theme_counter.most_common(20)),
            avg_rating=avg_rating,
            agents=list(agents_stats.values()),
        )

    return results


def fetch_and_analyze(
    discipline: Optional[str] = None,
    limit: int = 500,
) -> dict[str, DisciplineAnalysis]:
    """Lê agent_feedback do PostgreSQL e retorna análise agrupada."""
    if not is_db_enabled():
        logger.warning("Learning Loop v2: DB desabilitado — análise vazia")
        return {}

    try:
        with session_scope() as session:
            repo = DatabaseRepository(session)
            if discipline:
                rows = repo.list_feedback_by_discipline(discipline.upper(), limit=limit)
            else:
                rows = repo.list_all_feedback(limit=limit)
            return analyze_rows(rows)
    except Exception as exc:
        logger.warning("Learning Loop v2: falha na análise de feedback: %s", exc)
        return {}


def analysis_to_dict(analysis: DisciplineAnalysis) -> dict[str, Any]:
    return {
        "discipline": analysis.discipline,
        "agent_name": analysis.agent_name,
        "feedback_sample_size": analysis.feedback_sample_size,
        "low_quality_count": analysis.low_quality_count,
        "common_errors": analysis.common_errors,
        "frequent_themes": analysis.frequent_themes,
        "avg_rating": analysis.avg_rating,
        "error_patterns": analysis.error_patterns,
        "theme_counts": analysis.theme_counts,
    }
