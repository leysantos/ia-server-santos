"""
Geração de prompts otimizados com versionamento imutável.

Nunca sobrescreve versão anterior — cada otimização gera prompt_{slug}_v{N+1}.txt
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from experimental.learning_v2.discipline_profiles import (
    discipline_slug,
    ensure_dirs,
    get_latest_prompt_version,
    prompt_key_for,
    prompt_path_for,
)
from experimental.learning_v2.prompt_analyzer import BASE_PROMPT_INSTRUCTIONS, PromptGapAnalysis

logger = logging.getLogger(__name__)


class PromptVersionExistsError(FileExistsError):
    """Tentativa de sobrescrever prompt versionado."""


def build_optimized_prompt(
    discipline: str,
    version: int,
    gap_analysis: PromptGapAnalysis,
    common_errors: list[str],
    frequent_themes: list[str],
) -> str:
    """
    Monta prompt otimizado rule-based a partir de gaps e feedback real.
    Sem LLM — apenas enriquecimento determinístico das instruções.
    """
    normas = ", ".join(gap_analysis.normas) if gap_analysis.normas else "normas ABNT aplicáveis"
    slug = discipline_slug(discipline)
    key = prompt_key_for(discipline, version)

    errors_block = ""
    if common_errors:
        errors_block = "\nERROS A EVITAR (feedback real dos usuários):\n"
        for i, err in enumerate(common_errors[:8], 1):
            errors_block += f"- {err}\n"

    themes_block = ""
    if frequent_themes:
        themes_block = "\nTEMAS FREQUENTES (priorizar cobertura):\n"
        for theme in frequent_themes[:8]:
            themes_block += f"- {theme}\n"

    improvements_block = ""
    if gap_analysis.suggested_improvements:
        improvements_block = f"\nINSTRUÇÕES OTIMIZADAS (v{version} — Learning Loop v2):\n"
        for imp in gap_analysis.suggested_improvements:
            improvements_block += f"- {imp}\n"

    return f"""# {key}
# Disciplina: {discipline.upper()}
# Gerado automaticamente pelo Learning Loop v2 — não editar manualmente versões anteriores

Você é um engenheiro especialista em {discipline.upper()} do IA Server Santos.

DISCIPLINA: {discipline.upper()}
NORMAS DE REFERÊNCIA: {normas}
PROMPT_VERSION: {version}
PROMPT_KEY: {key}

{BASE_PROMPT_INSTRUCTIONS}
{improvements_block}{errors_block}{themes_block}
CONTEXTO NORMATIVO RECUPERADO (RAG v2):
{{context_block}}

SOLICITAÇÃO DO USUÁRIO:
{{user_input}}

RESPOSTA TÉCNICA ESTRUTURADA:"""


def save_prompt_version(
    discipline: str,
    version: int,
    content: str,
    *,
    allow_existing: bool = False,
) -> Path:
    """
    Salva nova versão de prompt. Falha se arquivo já existir (imutabilidade).
    """
    ensure_dirs()
    path = prompt_path_for(discipline, version)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not allow_existing:
        raise PromptVersionExistsError(
            f"Prompt {path.name} já existe — versionamento imutável; use versão superior."
        )

    path.write_text(content, encoding="utf-8")
    logger.info("Learning Loop v2: prompt salvo %s", path)
    return path


def load_prompt_version(discipline: str, version: int) -> Optional[str]:
    path = prompt_path_for(discipline, version)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def next_prompt_version(discipline: str) -> int:
    """Próxima versão disponível (max existente + 1)."""
    return get_latest_prompt_version(discipline) + 1


def optimize_prompt_for_discipline(
    discipline: str,
    gap_analysis: PromptGapAnalysis,
    common_errors: list[str],
    frequent_themes: list[str],
    *,
    force_version: Optional[int] = None,
) -> tuple[int, str, Path]:
    """
    Gera e persiste nova versão de prompt otimizado.
    Retorna (version, content, path).
    """
    version = force_version or next_prompt_version(discipline)
    content = build_optimized_prompt(
        discipline=discipline,
        version=version,
        gap_analysis=gap_analysis,
        common_errors=common_errors,
        frequent_themes=frequent_themes,
    )
    path = save_prompt_version(discipline, version, content)
    return version, content, path
