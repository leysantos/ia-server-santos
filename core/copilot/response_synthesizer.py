"""
Response Synthesizer — unifica respostas dos agentes em formato técnico estruturado.
"""

from __future__ import annotations

from typing import Any

from core.context_graph import ContextGraph
from core.copilot.execution_graph import ExecutionGraphResult
from core.copilot.task_planner import ExecutionPlan


def synthesize_response(
    plan: ExecutionPlan,
    execution: ExecutionGraphResult,
) -> dict[str, Any]:
    """
    Consolida respostas por disciplina em relatório técnico estruturado.
    """
    by_discipline: dict[str, dict[str, Any]] = {}
    sections: list[str] = []
    errors: list[str] = []

    for step_result in execution.step_results:
        disc = step_result.step.discipline
        text = (
            step_result.response.get("result")
            or step_result.response.get("response")
            or ""
        )
        by_discipline[disc] = {
            "discipline": disc,
            "agent": step_result.response.get("agent", step_result.step.agent),
            "step_id": step_result.step.step_id,
            "content": text,
            "success": step_result.success,
            "error": step_result.error,
            "extra": step_result.response.get("extra"),
        }

        status = "✓" if step_result.success else "✗"
        sections.append(f"## {status} {disc}\n\n{text}")

        if step_result.error:
            errors.append(disc)

    final_report = _build_final_report(plan, sections, errors)
    technical_summary = _build_technical_summary(by_discipline)

    return {
        "by_discipline": by_discipline,
        "technical_summary": technical_summary,
        "final_report": final_report,
        "disciplines": plan.disciplines,
        "step_count": len(execution.step_results),
        "completed_steps": execution.completed_count,
        "error_steps": execution.error_count,
        "errors": errors,
        "global_context": execution.context_graph.build_global_context(),
    }


def _build_technical_summary(by_discipline: dict[str, dict[str, Any]]) -> str:
    lines = ["# Resumo técnico multidisciplinar (Copilot v1)", ""]
    for disc, payload in by_discipline.items():
        content = payload.get("content", "")
        preview = content[:400] + ("..." if len(content) > 400 else "")
        lines.append(f"### {disc}")
        lines.append(preview)
        lines.append("")
    return "\n".join(lines).strip()


def _build_final_report(
    plan: ExecutionPlan,
    sections: list[str],
    errors: list[str],
) -> str:
    header = [
        "# Relatório Copilot — Engenharia Civil",
        "",
        f"**Intent:** {plan.intent}",
        f"**Disciplinas:** {', '.join(plan.disciplines)}",
        f"**Etapas:** {len(plan.steps)}",
        "",
    ]

    if errors:
        header.append(f"**Atenção:** falhas em {', '.join(errors)}")
        header.append("")

    body = "\n\n".join(sections)

    conclusion = [
        "",
        "---",
        "## Conclusão integrada",
        "",
        _build_conclusion(plan, errors),
    ]

    return "\n".join(header) + body + "\n".join(conclusion)


def _build_conclusion(plan: ExecutionPlan, errors: list[str]) -> str:
    if errors:
        return (
            f"Análise multidisciplinar parcialmente concluída para intent `{plan.intent}`. "
            f"Revise as disciplinas com falha: {', '.join(errors)}."
        )
    if plan.intent == "multi_discipline":
        return (
            "Análise multidisciplinar concluída. "
            "Considere validar premissas cruzadas entre disciplinas antes da execução de obra."
        )
    return (
        f"Análise técnica concluída para intent `{plan.intent}`. "
        "Valide premissas e normas citadas antes de aplicar em projeto executivo."
    )
