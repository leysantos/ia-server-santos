"""Testes de FKs em tabelas de audit/orçamento."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from core.database.models import AgentProposalRecord, AgentSimulationRecord, Base, BudgetDocument, Project
from core.database.repository import DatabaseRepository


def _setup_sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def test_budget_document_project_fk():
    db, engine = _setup_sqlite_session()
    project = Project(id=uuid.uuid4(), name="Obra teste")
    db.add(project)
    db.flush()

    doc = BudgetDocument(
        id=uuid.uuid4(),
        title="Orçamento teste",
        project_id=project.id,
        session_id="sess-1",
        payload={"session_id": "sess-1", "items": []},
    )
    db.add(doc)
    db.commit()

    inspector = inspect(engine)
    fks = inspector.get_foreign_keys("budget_documents")
    assert any(fk["referred_table"] == "projects" for fk in fks)

    loaded = db.get(BudgetDocument, doc.id)
    assert loaded is not None
    assert loaded.project_id == project.id
    assert loaded.to_summary()["project_id"] == str(project.id)


def test_agent_simulation_proposal_fk():
    db, engine = _setup_sqlite_session()
    repo = DatabaseRepository(db)
    proposal = repo.create_agent_proposal(
        {
            "name": "agent_test",
            "discipline": "ESTRUTURAL",
            "expected_improvement": 0.1,
            "risk_score": 0.2,
        }
    )
    simulation = repo.create_agent_simulation(
        {
            "proposal_id": str(proposal.id),
            "proposal_name": proposal.name,
            "discipline": proposal.discipline,
            "run_count": 1,
            "mode": "heuristic",
            "report": {"ok": True},
        }
    )
    db.commit()

    inspector = inspect(engine)
    fks = inspector.get_foreign_keys("agent_simulations")
    assert any(fk["referred_table"] == "agent_proposals" for fk in fks)

    loaded = db.get(AgentSimulationRecord, simulation.id)
    assert loaded is not None
    assert loaded.proposal_id == proposal.id


def test_agent_simulation_orphan_proposal_id_rejected():
    db, _engine = _setup_sqlite_session()
    row = AgentSimulationRecord(
        id=uuid.uuid4(),
        proposal_id=uuid.uuid4(),
        run_count=0,
    )
    db.add(row)
    try:
        db.commit()
        assert False, "FK deveria rejeitar proposal_id inexistente"
    except Exception:
        db.rollback()


if __name__ == "__main__":
    test_budget_document_project_fk()
    test_agent_simulation_proposal_fk()
    test_agent_simulation_orphan_proposal_id_rejected()
    print("OK: testes migrate_audit_fks passaram")
