"""Workflow de revisão (Módulo S)."""

from __future__ import annotations

from core.project_review.constants import ReviewStatus

_TRANSITIONS: dict[str, set[str]] = {
    ReviewStatus.RECEBIDO.value: {ReviewStatus.EM_PROCESSAMENTO.value},
    ReviewStatus.EM_PROCESSAMENTO.value: {
        ReviewStatus.ANALISADO.value,
        ReviewStatus.COM_PENDENCIAS.value,
    },
    ReviewStatus.ANALISADO.value: {
        ReviewStatus.COM_PENDENCIAS.value,
        ReviewStatus.AGUARDANDO_CORRECAO.value,
        ReviewStatus.REVISADO.value,
        ReviewStatus.APROVADO.value,
    },
    ReviewStatus.COM_PENDENCIAS.value: {ReviewStatus.AGUARDANDO_CORRECAO.value},
    ReviewStatus.AGUARDANDO_CORRECAO.value: {ReviewStatus.EM_PROCESSAMENTO.value, ReviewStatus.REVISADO.value},
    ReviewStatus.REVISADO.value: {ReviewStatus.APROVADO.value, ReviewStatus.COM_PENDENCIAS.value},
    ReviewStatus.APROVADO.value: set(),
}


def can_transition(current: str, target: str) -> bool:
    allowed = _TRANSITIONS.get(current, set())
    return target in allowed or current == target


def next_status_after_analysis(*, has_ncs: bool, scores: dict[str, float]) -> str:
    geral = scores.get("conformidade_geral", 0)
    if geral >= 85 and not has_ncs:
        return ReviewStatus.APROVADO.value
    if has_ncs:
        return ReviewStatus.COM_PENDENCIAS.value
    return ReviewStatus.ANALISADO.value
