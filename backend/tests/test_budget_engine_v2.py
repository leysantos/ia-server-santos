"""Testes Budget Engine v2, Quantity Engine e Budget Orchestrator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.bootstrap import load_default_bases, reset_providers, ensure_providers_registered
from pricing.budget.budget_calculator import BudgetCalculator
from pricing.budget.budget_engine_v2 import BudgetEngineV2
from pricing.budget.budget_session import SESSION_STORE
from pricing.orchestrator.budget_orchestrator import BudgetOrchestrator
from pricing.orchestrator.intent_parser import IntentParser
from pricing.quantity.quantity_engine import QuantityEngine

DATA_DIR = Path(__file__).resolve().parent.parent / "pricing" / "data"


def _setup():
    reset_providers()
    SESSION_STORE._sessions.clear()
    ensure_providers_registered()
    load_default_bases(DATA_DIR)


def test_passarela_structure_four_etapas():
    qe = QuantityEngine()
    intent = qe.enrich(
        {
            "scope": "passarela pedestre",
            "dimensions": {"length": 10, "width": 2},
        }
    )
    from pricing.budget.structure_engine import StructureEngine

    roots = StructureEngine().generate(intent)
    assert len(roots) == 4
    assert roots[0].code == "1"
    services = [c for r in roots for c in r.children]
    assert len(services) == 11
    estaca = next(c for c in services if "Estaca" in c.name)
    assert estaca.quantity == 20.0


def test_quantity_engine_area():
    qe = QuantityEngine()
    result = qe.enrich(
        {"scope": "alvenaria", "dimensions": {"length": 20, "height": 2.5}}
    )
    assert result["computed_quantities"]["area"] == round(20 * 2.5 * 1.05, 2)
    assert len(result["quantity_memory"]) >= 1


def test_intent_parser_fallback():
    parser = IntentParser(llm_client=None)
    intent = parser.parse(
        "Construir muro de 20 metros com 2,5m de altura em bloco estrutural",
        use_llm=False,
    )
    assert "alvenaria" in intent["scope"]
    assert intent["dimensions"]["length"] == 20
    assert intent["dimensions"]["height"] == 2.5


def test_budget_engine_v2_session_and_cell_edit():
    _setup()
    engine = BudgetEngineV2()
    session = engine.generate_session(
        {"scope": "alvenaria estrutural", "dimensions": {"length": 10, "height": 2}},
        source_priority=["sinapi"],
        title="Teste",
    )
    assert session.id
    assert session.grand_total > 0
    assert len(session.to_dict()["rows"]) > 0

    rows = session.to_dict()["rows"]
    leaf = next(r for r in rows if r["editable"] and r["unit_price"] > 0)
    before_total = session.grand_total
    updated = engine.update_cell(session.id, leaf["row_id"], "quantity", 999, code=leaf["code"])
    assert updated.grand_total != before_total


def test_budget_orchestrator_pipeline():
    _setup()
    orch = BudgetOrchestrator()
    result = orch.run(
        "muro 15m altura 2m bloco estrutural",
        source_priority=["sinapi"],
        use_llm=False,
    )
    assert result["session_id"]
    assert result["grand_total"] > 0
    assert "quantity_engine" in result["pipeline"]["steps"]
    assert result["pipeline"]["parser"] == "regex_fallback"


def test_budget_excel_export():
    _setup()
    engine = BudgetEngineV2()
    session = engine.generate_session(
        {"scope": "alvenaria", "dimensions": {"length": 5, "height": 2}},
        source_priority=["sinapi"],
    )
    xlsx = session.export_xlsx()
    assert xlsx[:2] == b"PK"


def test_api_generate_and_cell():
    from app.routes.pricing import BudgetGenerateRequest, generate_budget, update_budget_cell, CellUpdateRequest

    _setup()
    gen = generate_budget(
        BudgetGenerateRequest(
            text="muro 10m altura 2m bloco",
            use_llm=False,
            source_priority=["sinapi"],
        )
    )
    assert gen["grand_total"] > 0
    row = next(r for r in gen["rows"] if r["editable"] and r["unit_price"] > 0)
    updated = update_budget_cell(
        gen["session_id"],
        CellUpdateRequest(row_id=row["row_id"], code=row["code"], field="quantity", value=50),
    )
    assert updated["grand_total"] > 0
