"""
Patch Generator — gera propostas de mudança estruturada (JSON versionado).

Nenhuma auto-modificação — apenas propostas auditáveis.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from experimental.self_improving.learning_strategy_engine import StrategyDecision
from experimental.self_improving.meta_analyzer import MetaAnalysis

_PATCH_COUNTERS: dict[str, int] = {}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "geral"


def _next_version(patch_key: str) -> int:
    _PATCH_COUNTERS[patch_key] = _PATCH_COUNTERS.get(patch_key, 0) + 1
    return _PATCH_COUNTERS[patch_key]


def generate_patches(
    analysis: MetaAnalysis,
    strategies: list[StrategyDecision],
) -> list[dict[str, Any]]:
    """Gera patches JSON versionados a partir das estratégias aprovadas."""
    patches: list[dict[str, Any]] = []

    for strategy in strategies:
        primary_disc = strategy.disciplines[0] if strategy.disciplines else "geral"
        slug = _slug(f"{strategy.target}_{primary_disc}")
        patch_key = f"patch_{slug}"
        version = _next_version(patch_key)

        patch: dict[str, Any] = {
            "patch_key": patch_key,
            "patch_version": version,
            "patch_type": strategy.target,
            "status": "proposed",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_finding": strategy.source_finding,
            "disciplines": strategy.disciplines,
            "impact_score": strategy.impact,
            "risk_score": strategy.risk,
            "requires_validation": strategy.requires_validation,
            "rationale": strategy.rationale,
            "changes": _build_changes(strategy, analysis),
            "metadata": {
                "input_sample": analysis.input_text[:200],
                "intent": analysis.intent,
                "evaluation_final_score": analysis.evaluation.get("final_score"),
            },
        }
        patches.append(patch)

    return patches


def _build_changes(
    strategy: StrategyDecision,
    analysis: MetaAnalysis,
) -> dict[str, Any]:
    """Monta bloco `changes` específico por tipo de patch."""
    disc = strategy.disciplines[0] if strategy.disciplines else "GERAL"

    if strategy.target == "router_weights":
        return {
            "module": "core/router.py",
            "type": "router_weights",
            "proposal": {
                "discipline": disc,
                "action": strategy.action,
                "suggested_keywords": _suggest_keywords(analysis.input_text, disc),
                "weight_delta": 0.1,
            },
            "auto_apply": False,
        }

    if strategy.target == "rag_boosting":
        return {
            "module": "config/settings.py",
            "type": "rag_boosting",
            "proposal": {
                "discipline": disc,
                "RAG_BOOST_DISCIPLINE_delta": 0.05,
                "requires_index_validation": True,
            },
            "auto_apply": False,
        }

    if strategy.target == "prompt_update":
        return {
            "module": "core/learning_v2/",
            "type": "prompt_update",
            "proposal": {
                "discipline": disc,
                "action": strategy.action,
                "improvements": [
                    "Reforçar citação de NBRs por disciplina",
                    "Declarar premissas explicitamente",
                    f"Endereçar finding: {strategy.source_finding}",
                ],
            },
            "auto_apply": False,
        }

    if strategy.target == "agent_behavior":
        return {
            "module": "core/agents/",
            "type": "agent_behavior_tuning",
            "proposal": {
                "discipline": disc,
                "action": strategy.action,
                "note": "Proposta indireta via prompt — não altera código de agente",
                "suggested_output_sections": [
                    "Análise", "Premissas", "Recomendações", "Normas citadas",
                ],
            },
            "auto_apply": False,
        }

    return {
        "type": "generic",
        "proposal": {"action": strategy.action, "discipline": disc},
        "auto_apply": False,
    }


def _suggest_keywords(text: str, discipline: str) -> list[str]:
    tokens = re.findall(r"[a-záàâãéêíóôõúç]{4,}", text.lower())
    unique = list(dict.fromkeys(tokens))[:5]
    return unique or [discipline.lower()]
