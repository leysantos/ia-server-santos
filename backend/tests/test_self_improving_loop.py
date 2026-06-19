"""Testes Self-Improving Loop v1."""

import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import Base
from core.database.repository import DatabaseRepository
from core.self_improving.meta_analyzer import analyze_meta
from core.self_improving.learning_strategy_engine import decide_strategies
from core.self_improving.patch_generator import generate_patches
from core.self_improving.patch_validator import validate_patch
from core.self_improving.system_insights import run_self_improving_loop
from core.self_improving.failure_memory import record_failure, save_patch_proposal


def _low_score_copilot_output() -> dict:
    return {
        "input": "dimensionar prédio residencial",
        "conversation_id": str(uuid.uuid4()),
        "intent": "multi_discipline",
        "disciplines": ["ESTRUTURAL", "ORÇAMENTO"],
        "execution": [
            {
                "discipline": "ESTRUTURAL",
                "agent": "estruturas_agent",
                "success": True,
                "error": False,
                "response": {"result": "ok", "extra": {"rag": {}}},
            },
            {
                "discipline": "ORÇAMENTO",
                "agent": "orcamento_agent",
                "success": False,
                "error": True,
                "response": {"result": "erro", "error": True},
            },
        ],
        "result": {
            "by_discipline": {
                "ESTRUTURAL": {"content": "x" * 50},
                "ORÇAMENTO": {"content": "erro"},
            },
            "completed_steps": 1,
            "error_steps": 1,
        },
    }


def _low_score_evaluation() -> dict:
    return {
        "final_score": 0.45,
        "intent_accuracy": 0.55,
        "plan_quality": 0.70,
        "execution_completeness": 0.40,
        "response_quality": 0.35,
        "issues": ["etapas com falha"],
    }


def test_meta_analyzer_detects_failures():
    analysis = analyze_meta(_low_score_copilot_output(), _low_score_evaluation())
    assert analysis.has_failures
    types = {f.failure_type for f in analysis.findings}
    assert "low_final_score" in types
    assert "execution_failure" in types


def test_patch_generator_and_validator():
    analysis = analyze_meta(_low_score_copilot_output(), _low_score_evaluation())
    strategies = decide_strategies(analysis)
    assert strategies

    patches = generate_patches(analysis, strategies)
    assert patches
    assert patches[0]["patch_key"].startswith("patch_")
    assert patches[0]["changes"]["auto_apply"] is False

    validation = validate_patch(patches[0])
    assert validation.valid
    assert validation.status == "validated"


def test_run_self_improving_loop():
    result = run_self_improving_loop(
        _low_score_copilot_output(),
        _low_score_evaluation(),
    )
    assert result["success"] is True
    assert result["skipped"] is False
    assert result["findings"]
    assert result["patches_proposed"] >= 1


def test_persistence_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    import core.database.connection as conn_mod
    import experimental.self_improving.failure_memory as exp_fm_mod

    original = conn_mod.is_db_enabled

    @contextmanager
    def _scope():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    for mod in (conn_mod, exp_fm_mod):
        mod.is_db_enabled = lambda: True
        mod.session_scope = _scope

    failure = record_failure(
        input_text="teste",
        failure_type="execution_failure",
        route_decision={"disciplines": ["ESTRUTURAL"]},
        agent_used="estruturas_agent",
        evaluation_scores={"final_score": 0.4},
        suggested_fix="patch test",
    )
    assert failure is not None

    patch = save_patch_proposal({
        "patch_key": "patch_test_v1",
        "patch_version": 1,
        "patch_type": "prompt_update",
        "status": "validated",
        "risk_score": 0.2,
        "impact_score": 0.5,
        "changes": {"auto_apply": False},
    })
    assert patch is not None

    repo = DatabaseRepository(db)
    assert len(repo.list_system_failures()) == 1
    assert len(repo.list_system_patches()) == 1

    conn_mod.is_db_enabled = original


if __name__ == "__main__":
    test_meta_analyzer_detects_failures()
    test_patch_generator_and_validator()
    test_run_self_improving_loop()
    test_persistence_sqlite()
    print("OK: testes Self-Improving Loop v1 passaram")
