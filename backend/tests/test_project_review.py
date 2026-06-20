"""Testes — Project Review Engine (fundação)."""

from __future__ import annotations

import uuid

import pytest

from core.project_review.budget_analysis import analyze_budget
from core.project_review.compatibilization import analyze_compatibility
from core.project_review.constants import ReviewStatus
from core.project_review.digital_twin import build_twin_snapshot, empty_twin_payload
from core.project_review.discipline_detector import detect_discipline
from core.project_review.memorial_analysis import analyze_memorial
from core.project_review.nc_engine import compare_nc_versions, nc_from_agent_payload
from core.project_review.scoring_engine import compute_scores
from core.project_review.workflow import can_transition, next_status_after_analysis


def test_detect_discipline_estrutura():
    assert detect_discipline("EST-01-FUNDACOES.pdf") == "estrutura"


def test_detect_discipline_arquitetura():
    assert detect_discipline("ARQ-PLANTA-BAIXA.dwg") == "arquitetura"


def test_empty_twin_payload():
    twin = empty_twin_payload()
    assert "estrutura" in twin
    assert "arquitetura" in twin


def test_build_twin_snapshot():
    snapshot = build_twin_snapshot(
        project_id="p1",
        extractions=[
            {
                "file_id": "f1",
                "filename": "est.pdf",
                "discipline": "estrutura",
                "extraction_json": {"elementos_detectados": [{"tipo": "viga"}]},
            }
        ],
        normas=["NBR 6118"],
        version=1,
    )
    assert snapshot["versao"] == 1
    assert "estrutura" in snapshot["disciplinas"]


def test_nc_from_agent_payload():
    pid = uuid.uuid4()
    rid = uuid.uuid4()
    nc = nc_from_agent_payload(
        {"descricao": "Falta detalhe", "criticidade": "alta"},
        project_id=pid,
        review_id=rid,
        index=1,
    )
    assert nc["codigo"] == "NC-001"
    assert nc["criticidade"] == "alta"


def test_compute_scores():
    scores = compute_scores(
        analysis={"conflitos": [{"x": 1}]},
        nonconformities=[{"criticidade": "alta", "categoria": "estrutural"}],
    )
    assert 0 <= scores["conformidade_geral"] <= 100
    assert scores["conformidade_estrutural"] < 100


def test_workflow_transitions():
    assert can_transition(ReviewStatus.RECEBIDO.value, ReviewStatus.EM_PROCESSAMENTO.value)
    assert not can_transition(ReviewStatus.APROVADO.value, ReviewStatus.RECEBIDO.value)


def test_next_status_after_analysis():
    assert next_status_after_analysis(has_ncs=False, scores={"conformidade_geral": 90}) == ReviewStatus.APROVADO.value
    assert next_status_after_analysis(has_ncs=True, scores={"conformidade_geral": 90}) == ReviewStatus.COM_PENDENCIAS.value


def test_compare_nc_versions():
    prev = [{"codigo": "NC-001", "status": "aberta", "descricao": "A"}]
    curr = [{"codigo": "NC-001", "status": "corrigida", "descricao": "A"}]
    result = compare_nc_versions(prev, curr)
    assert len(result["corrigido"]) >= 1


def test_compatibilization():
    twin = {"payload": {"estrutura": {"documentos": [{}]}, "pci": {}}}
    report = analyze_compatibility(twin)
    assert report["total"] >= 0


def test_memorial_analysis():
    items = [
        {"filename": "memorial.docx", "discipline": "documentacao", "extraction_json": {"texto": "viga pilar laje"}},
        {"filename": "est.pdf", "discipline": "estrutura", "extraction_json": {"texto": "sapata", "elementos_detectados": []}},
    ]
    report = analyze_memorial(items)
    assert "descritos_nao_projetados" in report


def test_budget_analysis():
    report = analyze_budget(
        twin_payload={"payload": {}},
        extraction_items=[
            {"discipline": "orcamento", "format_key": "xlsx", "extraction_json": {"texto": "BDI 25%"}},
        ],
    )
    assert "score" in report
