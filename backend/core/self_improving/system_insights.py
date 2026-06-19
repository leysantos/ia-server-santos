"""
System Insights — orquestra Self-Improving Loop v1 e gera relatório auditável.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.self_improving.failure_memory import record_failure
from core.self_improving.learning_strategy_engine import decide_strategies
from core.self_improving.meta_analyzer import analyze_meta
from core.self_improving.patch_generator import generate_patches
from core.self_improving.patch_validator import validate_patches

logger = logging.getLogger(__name__)


def run_self_improving_loop(
    copilot_output: dict[str, Any],
    evaluation: dict[str, Any],
    *,
    risk_threshold: float = 0.7,
) -> dict[str, Any]:
    """
    Pipeline: evaluation → meta_analyzer → strategy → patch_generator → validator → log

    Fire-and-forget safe — nunca propaga exceções.
    """
    try:
        return _execute_loop(copilot_output, evaluation, risk_threshold=risk_threshold)
    except Exception as exc:
        logger.warning("Self-Improving Loop: falha no pipeline: %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_loop(
    copilot_output: dict[str, Any],
    evaluation: dict[str, Any],
    *,
    risk_threshold: float,
) -> dict[str, Any]:
    analysis = analyze_meta(copilot_output, evaluation)

    if not analysis.has_failures:
        return {
            "success": True,
            "skipped": True,
            "reason": "nenhuma falha detectada",
            "findings": [],
        }

    strategies = decide_strategies(analysis, risk_threshold=risk_threshold)
    patches = generate_patches(analysis, strategies)
    validations = validate_patches(patches, risk_threshold=risk_threshold)

    validated_patches = []
    for patch, validation in zip(patches, validations):
        patch["validation"] = validation.to_dict()
        patch["status"] = validation.status
        if validation.valid:
            validated_patches.append(patch)

    failures_logged = []
    for finding in analysis.findings:
        suggested = _suggest_fix_for_finding(finding, validated_patches)
        logged = record_failure(
            input_text=analysis.input_text,
            failure_type=finding.failure_type,
            route_decision={
                "intent": analysis.intent,
                "disciplines": analysis.disciplines,
                "agents": analysis.agents_used,
            },
            agent_used=analysis.agents_used[0] if analysis.agents_used else None,
            evaluation_scores=analysis.evaluation,
            suggested_fix=suggested,
            conversation_id=copilot_output.get("conversation_id"),
        )
        if logged:
            failures_logged.append(logged)

    patches_saved = _save_patches(validated_patches)

    insight = build_insights_report(analysis, strategies, patches, validations)

    logger.info(
        "Self-Improving Loop: findings=%d patches=%d validated=%d failures_logged=%d",
        len(analysis.findings),
        len(patches),
        len(validated_patches),
        len(failures_logged),
    )

    return {
        "success": True,
        "skipped": False,
        "findings": [
            {
                "failure_type": f.failure_type,
                "severity": f.severity,
                "description": f.description,
                "disciplines": f.disciplines,
            }
            for f in analysis.findings
        ],
        "strategies": [s.to_dict() for s in strategies],
        "patches_proposed": len(patches),
        "patches_validated": len(validated_patches),
        "patches": patches,
        "failures_logged": len(failures_logged),
        "insights": insight,
        "patches_saved": patches_saved,
    }


def _suggest_fix_for_finding(
    finding,
    patches: list[dict[str, Any]],
) -> str:
    related = [
        p for p in patches
        if finding.failure_type in (p.get("source_finding") or "")
        or any(d in (p.get("disciplines") or []) for d in finding.disciplines)
    ]
    if related:
        p = related[0]
        return f"{p['patch_key']} v{p['patch_version']}: {p.get('rationale', '')}"
    return finding.description


def _save_patches(patches: list[dict[str, Any]]) -> int:
    from core.self_improving.failure_memory import save_patch_proposal

    saved = 0
    for patch in patches:
        if save_patch_proposal(patch):
            saved += 1
    return saved


def build_insights_report(
    analysis,
    strategies,
    patches,
    validations,
) -> dict[str, Any]:
    return {
        "summary": {
            "input": analysis.input_text[:120],
            "intent": analysis.intent,
            "final_score": analysis.evaluation.get("final_score"),
            "findings_count": len(analysis.findings),
            "strategies_count": len(strategies),
            "patches_validated": sum(1 for v in validations if v.valid),
            "patches_rejected": sum(1 for v in validations if not v.valid),
        },
        "top_findings": [
            {"type": f.failure_type, "severity": f.severity, "desc": f.description}
            for f in sorted(analysis.findings, key=lambda x: x.severity, reverse=True)[:5]
        ],
        "recommended_actions": [
            f"{p['patch_key']} v{p['patch_version']} ({p['patch_type']})"
            for p in patches
            if p.get("status") == "validated"
        ][:5],
    }
