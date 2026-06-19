"""
Resolução de prompts versionados do Learning Loop v2 para uso em runtime.

Opt-in via USE_TUNED_PROMPTS — carrega a versão ativa do profile ou a mais recente.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from experimental.learning_v2.discipline_profiles import (
    get_latest_prompt_version,
    load_profile,
    prompt_key_for,
)
from experimental.learning_v2.prompt_optimizer import load_prompt_version

logger = logging.getLogger(__name__)


def _format_context_block(context: str) -> str:
    if context:
        return f"{context}\n"
    return "não disponível no índice. Baseie-se nas NBRs listadas.\n"


def get_active_prompt_version(discipline: str) -> tuple[int, Optional[dict[str, Any]]]:
    """
    Retorna (version, profile) da versão ativa para a disciplina.
    Profile indica versão pinada; senão usa a mais recente no filesystem.
    """
    profile = load_profile(discipline)
    if profile and profile.get("prompt_version", 0) > 0:
        return int(profile["prompt_version"]), profile

    latest = get_latest_prompt_version(discipline)
    return latest, profile


def resolve_tuned_prompt(
    discipline: str,
    user_input: str,
    context: str = "",
) -> Optional[tuple[str, dict[str, Any]]]:
    """
    Carrega e renderiza prompt versionado, se existir.

    Returns:
        (prompt_renderizado, metadata) ou None se não houver versão.
    """
    version, profile = get_active_prompt_version(discipline)
    if version <= 0:
        return None

    template = load_prompt_version(discipline, version)
    if not template:
        logger.debug("Learning Loop v2: template v%s ausente para %s", version, discipline)
        return None

    context_block = _format_context_block(context)
    try:
        prompt = template.format(context_block=context_block, user_input=user_input)
    except KeyError as exc:
        logger.warning(
            "Learning Loop v2: placeholder inválido no prompt %s v%s: %s",
            discipline,
            version,
            exc,
        )
        return None

    meta: dict[str, Any] = {
        "source": "learning_v2",
        "discipline": discipline.upper(),
        "prompt_version": version,
        "prompt_key": prompt_key_for(discipline, version),
    }
    if profile:
        meta["profile_updated_at"] = profile.get("updated_at")

    return prompt, meta
