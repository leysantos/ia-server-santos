"""
Meta Analyzer — detecta padrões de erro a partir de avaliações e histórico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.self_improving.failure_memory import (
    count_failures_by_discipline,
    count_failures_by_type,
)

FAILURE_THRESHOLD = 0.6
RECURRING_COUNT = 2


@dataclass
class MetaFinding:
    failure_type: str
    severity: float
    description: str
    disciplines: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetaAnalysis:
    input_text: str
    intent: str
    evaluation: dict[str, Any]
    findings: list[MetaFinding] = field(default_factory=list)
    disciplines: list[str] = field(default_factory=list)
    agents_used: list[str] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return len(self.findings) > 0

    @property
    def worst_severity(self) -> float:
        if not self.findings:
            return 0.0
        return max(f.severity for f in self.findings)


def analyze_meta(
    copilot_output: dict[str, Any],
    evaluation: dict[str, Any],
) -> MetaAnalysis:
    """
    Detecta erros recorrentes, routing fraco, falhas RAG e inconsistências entre agentes.
    """
    input_text = copilot_output.get("input") or ""
    intent = copilot_output.get("intent") or "general"
    disciplines = copilot_output.get("disciplines") or []
    execution = copilot_output.get("execution") or []
    agents_used = list({
        step.get("agent") or (step.get("response") or {}).get("agent")
        for step in execution
        if step.get("agent") or (step.get("response") or {}).get("agent")
    })

    analysis = MetaAnalysis(
        input_text=input_text,
        intent=intent,
        evaluation=evaluation,
        disciplines=disciplines,
        agents_used=[a for a in agents_used if a],
    )

    final_score = float(evaluation.get("final_score", 1.0))
    if final_score < FAILURE_THRESHOLD:
        analysis.findings.append(MetaFinding(
            failure_type="low_final_score",
            severity=1.0 - final_score,
            description=f"Score final baixo ({final_score})",
            disciplines=disciplines,
            evidence={"final_score": final_score, "issues": evaluation.get("issues", [])},
        ))

    # Routing / intent
    intent_acc = float(evaluation.get("intent_accuracy", 1.0))
    if intent_acc < FAILURE_THRESHOLD:
        analysis.findings.append(MetaFinding(
            failure_type="routing_low_performance",
            severity=1.0 - intent_acc,
            description=f"Baixa precisão de intent/routing ({intent_acc})",
            disciplines=disciplines,
            evidence={"intent_accuracy": intent_acc, "intent": intent},
        ))

    # Execution failures
    exec_score = float(evaluation.get("execution_completeness", 1.0))
    failed_steps = [s for s in execution if s.get("error") or not s.get("success")]
    if exec_score < FAILURE_THRESHOLD or failed_steps:
        failed_disc = [s.get("discipline") for s in failed_steps if s.get("discipline")]
        analysis.findings.append(MetaFinding(
            failure_type="execution_failure",
            severity=max(1.0 - exec_score, 0.5 if failed_steps else 0.0),
            description=f"Falhas de execução em {len(failed_steps)} etapa(s)",
            disciplines=failed_disc or disciplines,
            evidence={"execution_completeness": exec_score, "failed": failed_disc},
        ))

    # RAG failures
    rag_issues = _detect_rag_issues(copilot_output, evaluation)
    if rag_issues:
        analysis.findings.append(MetaFinding(
            failure_type="rag_failure",
            severity=0.7,
            description="Contexto RAG ausente ou insuficiente",
            disciplines=disciplines,
            evidence=rag_issues,
        ))

    # Agent inconsistency
    inconsistency = _detect_agent_inconsistency(execution)
    if inconsistency:
        analysis.findings.append(MetaFinding(
            failure_type="agent_inconsistency",
            severity=0.65,
            description="Respostas inconsistentes entre agentes",
            disciplines=inconsistency.get("disciplines", []),
            evidence=inconsistency,
        ))

    # Response quality
    resp_score = float(evaluation.get("response_quality", 1.0))
    if resp_score < FAILURE_THRESHOLD:
        analysis.findings.append(MetaFinding(
            failure_type="response_quality_low",
            severity=1.0 - resp_score,
            description=f"Qualidade de resposta baixa ({resp_score})",
            disciplines=disciplines,
            evidence={"response_quality": resp_score},
        ))

    # Recurring patterns from failure memory
    historical = _detect_recurring_patterns(disciplines)
    for disc, count in historical.items():
        if count >= RECURRING_COUNT:
            analysis.findings.append(MetaFinding(
                failure_type="recurring_discipline_error",
                severity=min(1.0, 0.4 + count * 0.15),
                description=f"Erros recorrentes em {disc} ({count} registros)",
                disciplines=[disc],
                evidence={"historical_count": count},
            ))

    type_counts = count_failures_by_type()
    for ft, count in type_counts.items():
        if count >= RECURRING_COUNT and ft not in {f.failure_type for f in analysis.findings}:
            analysis.findings.append(MetaFinding(
                failure_type="recurring_pattern",
                severity=min(1.0, 0.3 + count * 0.1),
                description=f"Padrão recorrente: {ft} ({count}x)",
                evidence={"failure_type": ft, "count": count},
            ))

    return analysis


def _detect_rag_issues(
    copilot_output: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    issues: dict[str, Any] = {}
    execution = copilot_output.get("execution") or []

    rag_missing = []
    for step in execution:
        resp = step.get("response") or {}
        extra = resp.get("extra") or {}
        rag = extra.get("rag") or {}
        if not rag.get("active") and not rag.get("context_length"):
            disc = step.get("discipline")
            if disc:
                rag_missing.append(disc)

    if rag_missing:
        issues["disciplines_without_rag"] = rag_missing

    eval_issues = evaluation.get("issues") or []
    rag_text_issues = [i for i in eval_issues if "rag" in i.lower() or "normativ" in i.lower()]
    if rag_text_issues:
        issues["evaluation_issues"] = rag_text_issues

    return issues


def _detect_agent_inconsistency(execution: list[dict]) -> Optional[dict[str, Any]]:
    if len(execution) < 2:
        return None

    success_disc = []
    error_disc = []
    lengths = []

    for step in execution:
        disc = step.get("discipline")
        resp = step.get("response") or {}
        text = resp.get("result") or resp.get("response") or ""
        if step.get("success"):
            success_disc.append(disc)
            lengths.append(len(text))
        elif step.get("error"):
            error_disc.append(disc)

    if success_disc and error_disc:
        variance = max(lengths) - min(lengths) if lengths else 0
        return {
            "disciplines": list(set(success_disc + error_disc)),
            "success": success_disc,
            "errors": error_disc,
            "content_length_variance": variance,
        }
    return None


def _detect_recurring_patterns(disciplines: list[str]) -> dict[str, int]:
    historical = count_failures_by_discipline()
    return {d: historical[d] for d in disciplines if historical.get(d, 0) >= RECURRING_COUNT}
