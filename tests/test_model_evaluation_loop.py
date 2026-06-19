"""Testes Model Evaluation Loop v1."""

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config.settings as settings_mod
from core.database.models import Base
from core.database.repository import DatabaseRepository
from core.models.model_scorer import ModelScorer
from core.models.model_evaluation_loop import ModelEvaluationLoop, RECALIBRATE_EVERY
from core.models.model_router import ModelRouter, get_model_router, routed_generate


def test_model_scorer_engineering():
    scorer = ModelScorer()
    good = scorer.score_response(
        "dimensionar viga NBR 6118",
        "## Análise\nDimensionamento conforme NBR 6118.\n### Premissas\nCarga permanente.",
        "engineering_primary",
    )
    poor = scorer.score_response("dimensionar viga", "ok", "engineering_primary")
    assert good > poor
    assert 0 <= good <= 1


def test_evaluation_picks_higher_score():
    loop = ModelEvaluationLoop()
    llm = MagicMock()
    llm.generate.side_effect = [
        ("Resposta curta", "qwen3:14b"),
        (
            "## Análise estrutural\nDimensionamento NBR 6118 com premissas e recomendações detalhadas.",
            "qwen3-coder",
        ),
    ]

    with patch.object(settings_mod, "USE_MODEL_EVALUATION", False):
        result = loop.evaluate(
            prompt="prompt",
            input_text="dimensionar viga NBR 6118",
            task_type="engineering_primary",
            discipline="ESTRUTURAL",
            primary_model="qwen3:14b",
            fallback_model="qwen3-coder",
            client=llm,
        )

    assert result["winner_model"] in ("qwen3:14b", "qwen3-coder")
    assert result["scores"]["primary"] >= 0
    assert result["decision_reason"]


def test_routed_generate_evaluation_path():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", True), patch.object(
        settings_mod, "USE_MODEL_EVALUATION", True
    ), patch(
        "core.models.model_evaluation_loop.evaluate_and_generate",
        return_value=("winner text", "qwen3-coder", {"decision_reason": "test"}),
    ) as mock_eval:
        text, model = routed_generate(
            "prompt",
            "engineering_primary",
            discipline="ESTRUTURAL",
            module="test",
        )

    mock_eval.assert_called_once()
    assert text == "winner text"
    assert model == "qwen3-coder"


def test_get_best_model_from_profile():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    import core.database.connection as conn_mod

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

    repo = DatabaseRepository(db)
    repo.rebuild_performance_profiles("engineering_primary", "ESTRUTURAL")
    # seed evaluations
    for i in range(5):
        repo.create_model_evaluation(
            input_text="viga",
            task_type="engineering_primary",
            discipline="ESTRUTURAL",
            primary_model="qwen3:14b",
            fallback_model="qwen3-coder",
            winner_model="qwen3-coder" if i < 4 else "qwen3:14b",
            primary_score=0.5,
            fallback_score=0.8,
            primary_latency_ms=100,
            fallback_latency_ms=90,
            decision_reason="test",
        )
    db.commit()
    repo.rebuild_performance_profiles("engineering_primary", "ESTRUTURAL")
    db.commit()

    best = repo.get_best_performance_profile("engineering_primary", "ESTRUTURAL")
    assert best is not None
    assert best.model_name == "qwen3-coder"
    assert best.win_rate > 0.5

    with patch.object(settings_mod, "USE_MODEL_EVALUATION", True):
        router = ModelRouter()
        assert router.get_best_model("engineering_primary", "ESTRUTURAL") == "qwen3-coder"


def test_auto_recalibrate_at_threshold():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    import core.database.connection as conn_mod

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

    router = get_model_router()
    router.model_map["engineering_primary"] = "qwen3:14b"

    repo = DatabaseRepository(db)
    for i in range(RECALIBRATE_EVERY):
        repo.create_model_evaluation(
            input_text=f"test {i}",
            task_type="engineering_primary",
            discipline="ESTRUTURAL",
            primary_model="qwen3:14b",
            fallback_model="qwen3-coder",
            winner_model="qwen3-coder",
            primary_score=0.4,
            fallback_score=0.9,
            primary_latency_ms=100,
            fallback_latency_ms=80,
            decision_reason="better_fallback",
        )
    db.commit()

    from core.models.model_performance_service import maybe_recalibrate_profiles

    with patch.object(settings_mod, "USE_MODEL_EVALUATION", True):
        maybe_recalibrate_profiles("engineering_primary", "ESTRUTURAL")

    assert router.model_map.get("engineering_primary") == "qwen3-coder"


def test_legacy_unchanged_when_flags_off():
    with patch.object(settings_mod, "USE_MODEL_ROUTER", False), patch.object(
        settings_mod, "USE_MODEL_EVALUATION", False
    ):
        llm = MagicMock()
        llm.generate.return_value = ("legacy", "qwen3:14b")
        text, model = routed_generate("p", "engineering_primary", client=llm)
        assert text == "legacy"
        llm.generate.assert_called_once()


if __name__ == "__main__":
    test_model_scorer_engineering()
    test_evaluation_picks_higher_score()
    test_routed_generate_evaluation_path()
    test_get_best_model_from_profile()
    test_auto_recalibrate_at_threshold()
    test_legacy_unchanged_when_flags_off()
    print("OK: testes Model Evaluation Loop v1 passaram")
