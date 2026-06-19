"""Testes Evaluation Loop v2 — scores, pipeline e persistência."""

import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import Base
from core.database.repository import DatabaseRepository
from core.evaluation_v2.evaluation_engine import evaluate
from core.evaluation_v2.evaluation_logger import save_evaluation
from core.evaluation_v2.intent_evaluator import evaluate_intent
from core.evaluation_v2.plan_evaluator import evaluate_plan
from core.evaluation_v2.execution_evaluator import evaluate_execution
from core.evaluation_v2.response_evaluator import evaluate_response


def _sample_copilot_output() -> dict:
    return {
        "input": "dimensionar prédio residencial",
        "conversation_id": str(uuid.uuid4()),
        "intent": "multi_discipline",
        "intent_confidence": 0.85,
        "matched_categories": ["structural"],
        "disciplines": ["ARQUITETURA", "ESTRUTURAL", "ORÇAMENTO"],
        "plan": [
            {
                "step_id": "step_1",
                "order": 1,
                "discipline": "ARQUITETURA",
                "agent": "arquitetura_agent",
                "depends_on": [],
                "use_context": False,
            },
            {
                "step_id": "step_2",
                "order": 2,
                "discipline": "ESTRUTURAL",
                "agent": "estruturas_agent",
                "depends_on": ["ARQUITETURA"],
                "use_context": True,
            },
            {
                "step_id": "step_3",
                "order": 3,
                "discipline": "ORÇAMENTO",
                "agent": "orcamento_agent",
                "depends_on": ["ESTRUTURAL"],
                "use_context": True,
            },
        ],
        "execution": [
            {"discipline": "ARQUITETURA", "success": True, "error": False},
            {"discipline": "ESTRUTURAL", "success": True, "error": False},
            {"discipline": "ORÇAMENTO", "success": False, "error": True},
        ],
        "context_graph": {
            "nodes": {
                "ARQUITETURA": {"data": {"result": "ok"}},
                "ESTRUTURAL": {"data": {"result": "ok"}},
            }
        },
        "result": {
            "by_discipline": {
                "ARQUITETURA": {"content": "Análise arquitetônica " + "x" * 100},
                "ESTRUTURAL": {"content": "Dimensionamento NBR 6118 " + "x" * 100},
                "ORÇAMENTO": {"content": "erro"},
            },
            "final_report": "## ARQUITETURA\n\nAnálise\n\n## ESTRUTURAL\n\nNBR 6118",
            "technical_summary": "Resumo técnico",
            "completed_steps": 2,
            "error_steps": 1,
        },
        "evaluation": {"score": 0.72, "grade": "bom"},
    }


def test_individual_evaluators():
    output = _sample_copilot_output()

    intent_score = evaluate_intent(output)
    plan_score = evaluate_plan(output)
    exec_score = evaluate_execution(output)
    resp_score = evaluate_response(output)

    assert 0.0 <= intent_score.score <= 1.0
    assert 0.0 <= plan_score.score <= 1.0
    assert 0.0 <= exec_score.score <= 1.0
    assert 0.0 <= resp_score.score <= 1.0
    assert exec_score.score < 1.0  # uma etapa falhou


def test_evaluation_engine_pipeline():
    result = evaluate(_sample_copilot_output())

    assert "intent_accuracy" in result
    assert "plan_quality" in result
    assert "execution_completeness" in result
    assert "response_quality" in result
    assert "final_score" in result
    assert 0.0 <= result["final_score"] <= 1.0
    assert len(result["stages"]) == 4
    assert isinstance(result["issues"], list)


def test_save_evaluation_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    import core.database.connection as conn_mod
    import core.evaluation_v2.evaluation_logger as logger_mod

    original = conn_mod.is_db_enabled

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
    logger_mod.is_db_enabled = lambda: True
    logger_mod.session_scope = _scope

    evaluation = evaluate(_sample_copilot_output())
    saved = save_evaluation(evaluation)

    assert saved is not None
    assert saved["final_score"] == evaluation["final_score"]
    assert saved["intent"] == "multi_discipline"

    rows = DatabaseRepository(db).list_copilot_evaluations()
    assert len(rows) == 1

    conn_mod.is_db_enabled = original


if __name__ == "__main__":
    test_individual_evaluators()
    test_evaluation_engine_pipeline()
    test_save_evaluation_sqlite()
    print("OK: testes Evaluation Loop v2 passaram")
