"""Testes — módulo Workflow Projetos (Fase 1)."""

from __future__ import annotations

import uuid

import pytest

from core.workflow.events.types import DEFAULT_FOLDER_STRUCTURE, WorkflowEventType
from core.workflow.template_engine.engine import build_sheet_context, render_template


def test_default_folder_structure_count():
    assert len(DEFAULT_FOLDER_STRUCTURE) == 12
    paths = {f["path"] for f in DEFAULT_FOLDER_STRUCTURE}
    assert "Pranchas" in paths
    assert "As_Built" in paths


def test_template_placeholders():
    ctx = build_sheet_context(
        empresa="Santos Eng",
        autor="Eng. Silva",
        crea="123456",
        escala="1:50",
        titulo="Planta Baixa",
        codigo="ARQ-01",
        revisao="REV01",
        data="20/06/2026",
    )
    rendered = render_template("{{empresa}} — {{titulo}} — {{escala}} — {{revisao}}", ctx)
    assert "Santos Eng" in rendered
    assert "1:50" in rendered
    assert "REV01" in rendered


def test_revision_code_increment():
    from core.workflow.agents.specialists import _next_revision_code

    assert _next_revision_code("REV00") == "REV01"
    assert _next_revision_code("REV09") == "REV10"


def test_drawing_detector_pci():
    from core.workflow.agents.specialists import DrawingDetectorAgent

    agent = DrawingDetectorAgent()
    result = agent.run({"filename": "planta_pci_hidrantes.dwg", "metadata": {"layers": []}})
    assert result["classificacao"] == "pci"
    assert result["disciplina"] == "incendio"


def test_scale_agent_default():
    from core.workflow.agents.specialists import ScaleAgent

    agent = ScaleAgent()
    result = agent.run({"filename": "planta.dwg", "metadata": {}})
    assert result["escala"] == "1:100"


def test_event_types_complete():
    expected = {
        "PROJECT_CREATED",
        "FILE_UPLOADED",
        "DWG_ANALYZED",
        "SHEET_GENERATED",
        "DELIVERY_COMPLETED",
    }
    values = {e.value for e in WorkflowEventType}
    assert expected.issubset(values)


@pytest.mark.skipif(True, reason="Requer PostgreSQL de integração")
def test_workflow_initialize_integration():
    pass
