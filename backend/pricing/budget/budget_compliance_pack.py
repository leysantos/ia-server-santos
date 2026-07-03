"""Pacote de compliance licitação — checklist Lei 14.133 / TCU (B22)."""

from __future__ import annotations

import json
from typing import Any

from pricing.budget.budget_session import BudgetSession
from pricing.budget.bdi_edital_validator import bdi_checklist_status


def build_compliance_pack(session: BudgetSession) -> dict[str, Any]:
    """Metadados e checklist para prestação de contas / defesa em licitação."""
    project = session.project
    bdi = project.bdi
    audit_actions = sorted({e.get("action") for e in session.audit_log if e.get("action")})
    bdi_validation_status = bdi_checklist_status(bdi)
    return {
        "session_id": session.id,
        "title": session.title,
        "projeto": project.projeto,
        "orgao": project.orgao,
        "processo": project.processo,
        "obra_type": project.obra_type,
        "grand_total": session.grand_total,
        "grand_total_comd": session.grand_total_comd,
        "grand_total_semd": session.grand_total_semd,
        "desoneracao_mode": session.desoneracao_mode,
        "bdi": bdi.to_dict(),
        "bdi_validation_status": bdi_validation_status,
        "audit_actions": audit_actions,
        "audit_entry_count": len(session.audit_log),
        "checklist_lei_14133": [
            {"id": "L1", "item": "Memória de cálculo (MCQ) disponível", "status": "ok" if session.calculation_memory else "pendente"},
            {"id": "L2", "item": "Orçamento analítico ComD/SemD", "status": "ok"},
            {"id": "L3", "item": "BDI documentado e validado vs edital", "status": bdi_validation_status},
            {"id": "L4", "item": "Trilha de auditoria de alterações", "status": "ok" if audit_actions else "pendente"},
            {"id": "L5", "item": "Cronograma físico-financeiro", "status": "ok" if session.schedule else "pendente"},
            {"id": "L6", "item": "Publicação PNCP", "status": "manual"},
            {"id": "L7", "item": "Prestação de contas TCU", "status": "manual"},
        ],
        "export_native_docs": [
            "orc_sintetico",
            "orc_analitico",
            "mcq",
            "cronograma",
            "curva_abc",
            "curva_s",
        ],
        "export_official_xlsm": bool(session.intent.get("ppd_workbook")),
        "nota": "Pacote técnico gerado pelo IA Server Santos — itens 'manual' exigem fluxo institucional.",
    }


def compliance_pack_json(session: BudgetSession) -> bytes:
    return json.dumps(build_compliance_pack(session), ensure_ascii=False, indent=2).encode("utf-8")
