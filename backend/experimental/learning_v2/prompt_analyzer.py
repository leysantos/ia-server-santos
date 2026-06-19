"""
Análise de prompts base — identifica lacunas a partir do feedback analisado.

Não altera agentes existentes; espelha o template de BaseAgentIntelligent para referência.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.agents.base_agent_intelligent import DISCIPLINE_NBRS
from experimental.learning_v2.feedback_analyzer import DisciplineAnalysis

# Template base (referência estática — não modifica BaseAgentIntelligent)
BASE_PROMPT_INSTRUCTIONS = """INSTRUÇÕES:
- Responda em português técnico, claro e estruturado
- Cite NBRs e requisitos normativos quando aplicável
- Organize a resposta em seções: Análise, Premissas, Recomendações, Normas citadas
- Se o usuário pedir tabelas normativas, reproduza-as de forma organizada (markdown)
- Se faltar dado, declare premissas explicitamente
- Não invente valores numéricos sem base normativa ou contexto fornecido
- Priorize segurança, conformidade normativa e boas práticas de engenharia civil"""


@dataclass
class PromptGapAnalysis:
    discipline: str
    normas: list[str]
    gaps: list[str] = field(default_factory=list)
    suggested_improvements: list[str] = field(default_factory=list)


ERROR_IMPROVEMENT_MAP = {
    "nbr": "Sempre cite explicitamente a NBR aplicável e o item/tabela relevante",
    "incomplet": "Inclua seção de Premissas e Recomendações mesmo quando dados faltarem",
    "tabela": "Reproduza tabelas normativas solicitadas em markdown estruturado",
    "premissa": "Declare todas as premissas adotadas antes dos cálculos ou conclusões",
    "generico": "Evite respostas genéricas; detalhe passos técnicos específicos da disciplina",
    "rag": "Priorize e referencie o contexto normativo recuperado pelo RAG quando disponível",
    "correcao": "Incorpore correções frequentes dos usuários nas respostas futuras",
}


def _match_improvements_from_errors(common_errors: list[str]) -> list[str]:
    improvements: list[str] = []
    seen: set[str] = set()
    for error in common_errors:
        error_lower = error.lower()
        for keyword, improvement in ERROR_IMPROVEMENT_MAP.items():
            if keyword in error_lower and improvement not in seen:
                improvements.append(improvement)
                seen.add(improvement)
    return improvements


def analyze_prompt_gaps(analysis: DisciplineAnalysis) -> PromptGapAnalysis:
    """
    Deriva melhorias de prompt a partir de padrões de feedback.
    Rule-based — sem LLM.
    """
    discipline = analysis.discipline
    normas = DISCIPLINE_NBRS.get(discipline, ["normas ABNT aplicáveis"])
    gaps: list[str] = []
    improvements: list[str] = []

    if analysis.low_quality_count > 0:
        rate = analysis.low_quality_count / max(analysis.feedback_sample_size, 1)
        gaps.append(
            f"{analysis.low_quality_count} respostas com rating <= 2 "
            f"({rate:.0%} da amostra)"
        )

    if analysis.avg_rating is not None and analysis.avg_rating < 3.5:
        gaps.append(f"Rating médio baixo: {analysis.avg_rating}/5")

    if analysis.common_errors:
        gaps.append(f"{len(analysis.common_errors)} padrões de erro identificados no feedback")

    improvements.extend(_match_improvements_from_errors(analysis.common_errors))

    if analysis.frequent_themes:
        top_themes = ", ".join(analysis.frequent_themes[:5])
        improvements.append(
            f"Antecipe temas frequentes dos usuários: {top_themes}"
        )

    if analysis.low_quality_count >= 2 and "rag" not in " ".join(improvements).lower():
        improvements.append(
            "Quando houver contexto RAG, cite trechos e referências normativas recuperadas"
        )

    # Deduplicate preserving order
    seen: set[str] = set()
    unique_improvements = []
    for item in improvements:
        if item not in seen:
            unique_improvements.append(item)
            seen.add(item)

    return PromptGapAnalysis(
        discipline=discipline,
        normas=normas,
        gaps=gaps,
        suggested_improvements=unique_improvements,
    )


def get_base_instructions() -> str:
    return BASE_PROMPT_INSTRUCTIONS


def get_normas_for_discipline(discipline: str) -> list[str]:
    return DISCIPLINE_NBRS.get(discipline.upper(), [])
