"""Testes AED v1 — pipeline completo."""

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.aed.project_understanding import understand_project
from core.aed.design_generator import generate_designs, MIN_OPTIONS_PER_DISCIPLINE
from core.aed.engineering_simulator import simulate_designs
from core.aed.comparison_engine import compare_solutions
from core.aed.selection_engine import select_best_solution
from core.aed.report_generator import generate_report
from core.aed.aed_orchestrator import run_aed
from core.database.models import Base
from core.database.repository import DatabaseRepository


def test_project_understanding():
    u = understand_project("dimensionar prédio residencial com estrutura")
    assert u.intent == "multi_discipline"
    assert "ESTRUTURAL" in u.disciplines
    assert u.objectives


def test_design_generator_min_two_options():
    u = understand_project("dimensionar viga de concreto armado")
    designs = generate_designs(u)
    by_disc = {}
    for d in designs:
        by_disc.setdefault(d.discipline, []).append(d)
    for disc, opts in by_disc.items():
        assert len(opts) >= MIN_OPTIONS_PER_DISCIPLINE, f"{disc} tem {len(opts)} opções"


def test_full_pipeline():
    with patch("core.aed.engineering_simulator.get_rag_engine") as mock_rag:
        mock_rag.return_value.build_context.return_value = "NBR 6118 requisitos " * 20
        result = run_aed("dimensionar prédio residencial", use_rag=True, persist=False)

    assert result["understanding"]
    assert len(result["designs"]) >= 4
    assert len(result["simulations"]) == len(result["designs"])
    assert result["comparison"]["rankings"]
    assert result["selection"]["selected_option_id"]
    assert result["report"]["final_report"]
    assert "Solução selecionada" in result["report"]["final_report"]


def test_simulation_and_selection():
    u = understand_project("dimensionar viga de concreto")
    designs = generate_designs(u)
    with patch("core.aed.engineering_simulator.get_rag_engine") as mock_rag:
        mock_rag.return_value.build_context.return_value = "NBR 6118"
        sims = simulate_designs(u, designs, use_rag=True)
    comparison = compare_solutions(designs, sims)
    selection = select_best_solution(u, designs, comparison, sims)
    report = generate_report(u, designs, sims, comparison, selection)

    assert all(0 <= s.final_simulation_score <= 1 for s in sims)
    assert selection.final_selection_score > 0
    assert report["risks"]


def test_persistence_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    import core.database.connection as conn_mod
    import core.aed.audit as audit_mod

    @contextmanager
    def _scope():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    conn_mod.is_db_enabled = lambda: True
    conn_mod.session_scope = _scope
    audit_mod.is_db_enabled = lambda: True
    audit_mod.session_scope = _scope

    with patch("core.aed.engineering_simulator.get_rag_engine") as mock_rag:
        mock_rag.return_value.build_context.return_value = ""
        result = run_aed("dimensionar viga", use_rag=False, persist=True)

    assert result.get("aed_run_id")
    assert len(DatabaseRepository(db).list_aed_runs()) == 1


if __name__ == "__main__":
    test_project_understanding()
    test_design_generator_min_two_options()
    test_full_pipeline()
    test_simulation_and_selection()
    test_persistence_sqlite()
    print("OK: testes AED v1 passaram")
