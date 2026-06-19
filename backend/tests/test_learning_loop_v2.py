"""Testes Learning Loop v2 — profiles, otimização e versionamento."""

import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from core.database.models import Base
from core.database.repository import DatabaseRepository
from core.learning_v2.discipline_profiles import (
    get_latest_prompt_version,
    load_profile,
    prompt_key_for,
    prompt_path_for,
    save_profile,
)
from core.learning_v2.feedback_analyzer import analyze_rows, fetch_and_analyze
from core.learning_v2.prompt_analyzer import analyze_prompt_gaps
from core.learning_v2.prompt_optimizer import (
    PromptVersionExistsError,
    build_optimized_prompt,
    optimize_prompt_for_discipline,
    save_prompt_version,
)
from core.learning_v2.auto_tuner import run_auto_tune, tune_discipline


def _setup_sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _seed_estrutural_feedback(db):
    repo = DatabaseRepository(db)
    for i in range(4):
        repo.create_agent_feedback(
            agent_name="estruturas_agent",
            discipline="ESTRUTURAL",
            input_text=f"dimensionar viga concreto armado {i}",
            response_text="Resposta genérica sem NBR",
            rating=1 if i < 2 else 4,
            feedback_text="Resposta incompleta, faltou citar NBR 6118" if i < 2 else None,
            corrected_answer="Deveria citar NBR 6118 tabela 6.3" if i == 0 else None,
        )
    db.commit()
    return repo


def _patch_learning_dirs(tmp_path: Path):
    profiles = tmp_path / "profiles"
    prompts = tmp_path / "prompts"
    profiles.mkdir()
    prompts.mkdir()
    settings.LEARNING_V2_DIR = tmp_path
    settings.LEARNING_V2_PROFILES_DIR = profiles
    settings.LEARNING_V2_PROMPTS_DIR = prompts

    import core.learning_v2.discipline_profiles as profiles_mod
    import core.learning_v2.prompt_optimizer as optimizer_mod
    import experimental.learning_v2.discipline_profiles as exp_profiles_mod
    import experimental.learning_v2.prompt_optimizer as exp_optimizer_mod

    for mod in (profiles_mod, optimizer_mod, exp_profiles_mod, exp_optimizer_mod):
        mod.LEARNING_V2_DIR = tmp_path
        mod.LEARNING_V2_PROFILES_DIR = profiles
        mod.LEARNING_V2_PROMPTS_DIR = prompts


def test_feedback_analysis_grouping():
    db = _setup_sqlite_session()
    _seed_estrutural_feedback(db)
    rows = DatabaseRepository(db).list_all_feedback()
    analyses = analyze_rows(rows)

    assert "ESTRUTURAL" in analyses
    analysis = analyses["ESTRUTURAL"]
    assert analysis.feedback_sample_size == 4
    assert analysis.low_quality_count == 2
    assert analysis.agent_name == "estruturas_agent"
    assert len(analysis.frequent_themes) >= 1


def test_profile_generation_and_prompt_optimization():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _patch_learning_dirs(tmp_path)

        db = _setup_sqlite_session()
        _seed_estrutural_feedback(db)
        rows = DatabaseRepository(db).list_all_feedback()
        analysis = analyze_rows(rows)["ESTRUTURAL"]
        gap = analyze_prompt_gaps(analysis)

        assert gap.suggested_improvements
        assert any("NBR" in imp for imp in gap.suggested_improvements)

        version, content, path = optimize_prompt_for_discipline(
            discipline="ESTRUTURAL",
            gap_analysis=gap,
            common_errors=analysis.common_errors,
            frequent_themes=analysis.frequent_themes,
        )

        assert version == 1
        assert path.exists()
        assert "prompt_estrutural_v1" in content
        assert "INSTRUÇÕES OTIMIZADAS (v1" in content

        profile = {
            "discipline": "ESTRUTURAL",
            "prompt_version": version,
            "prompt_key": prompt_key_for("ESTRUTURAL", version),
            "agent_name": "estruturas_agent",
            "common_errors": analysis.common_errors,
            "improvements": gap.suggested_improvements,
            "frequent_themes": analysis.frequent_themes,
            "feedback_sample_size": analysis.feedback_sample_size,
            "low_quality_count": analysis.low_quality_count,
        }
        saved = save_profile(profile)

        loaded = load_profile("ESTRUTURAL")
        assert loaded is not None
        assert loaded["prompt_version"] == 1
        assert loaded["common_errors"] == analysis.common_errors
        assert saved["discipline"] == "ESTRUTURAL"


def test_prompt_versioning_never_overwrites():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _patch_learning_dirs(tmp_path)

        db = _setup_sqlite_session()
        _seed_estrutural_feedback(db)
        analysis = analyze_rows(DatabaseRepository(db).list_all_feedback())["ESTRUTURAL"]
        gap = analyze_prompt_gaps(analysis)

        v1_content = build_optimized_prompt(
            "ESTRUTURAL", 1, gap, analysis.common_errors, analysis.frequent_themes
        )
        save_prompt_version("ESTRUTURAL", 1, v1_content)
        assert get_latest_prompt_version("ESTRUTURAL") == 1

        try:
            save_prompt_version("ESTRUTURAL", 1, "tentativa sobrescrever")
            raise AssertionError("deveria falhar ao sobrescrever v1")
        except PromptVersionExistsError:
            pass

        v2, _, path_v2 = optimize_prompt_for_discipline(
            discipline="ESTRUTURAL",
            gap_analysis=gap,
            common_errors=analysis.common_errors,
            frequent_themes=analysis.frequent_themes,
        )
        assert v2 == 2
        assert path_v2.exists()
        assert prompt_path_for("ESTRUTURAL", 1).read_text(encoding="utf-8") == v1_content
        assert get_latest_prompt_version("ESTRUTURAL") == 2


def test_auto_tune_integration():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _patch_learning_dirs(tmp_path)

        db = _setup_sqlite_session()
        _seed_estrutural_feedback(db)

        import core.database.connection as conn_mod
        import core.learning_v2.feedback_analyzer as analyzer_mod
        import experimental.learning_v2.feedback_analyzer as exp_analyzer_mod
        import experimental.learning_v2.auto_tuner as exp_auto_mod

        original_enabled = conn_mod.is_db_enabled

        @contextmanager
        def _scope():
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        for mod in (conn_mod, analyzer_mod, exp_analyzer_mod, exp_auto_mod):
            mod.is_db_enabled = lambda: True
            mod.session_scope = _scope

        report = run_auto_tune(discipline="ESTRUTURAL", min_feedback=3)
        assert report.tuned_count == 1
        assert report.results[0].prompt_key == "prompt_estrutural_v1"

        profile = load_profile("ESTRUTURAL")
        assert profile is not None
        assert profile["prompt_version"] == 1
        assert profile["improvements"]

        conn_mod.is_db_enabled = original_enabled


if __name__ == "__main__":
    test_feedback_analysis_grouping()
    test_profile_generation_and_prompt_optimization()
    test_prompt_versioning_never_overwrites()
    test_auto_tune_integration()
    print("OK: testes Learning Loop v2 passaram")
