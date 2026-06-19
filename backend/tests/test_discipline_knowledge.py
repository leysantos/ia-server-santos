"""Testes da reestruturação flat (metadata-driven)."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.knowledge.resolver import (
    DISCIPLINE_SLUGS,
    get_knowledge_path,
    get_path,
    file_dedup_key,
    file_hash_dedup_key,
    legacy_kb_subdir_to_discipline,
    normalize_discipline_slug,
)
from core.knowledge.router import route_knowledge


def test_get_knowledge_path_resolution():
    from config.settings import KNOWLEDGE_DOCUMENTS_DIR

    assert get_knowledge_path("ESTRUTURAL", "raw") == KNOWLEDGE_DOCUMENTS_DIR
    assert get_knowledge_path("ORÇAMENTO", "embeddings") == KNOWLEDGE_DOCUMENTS_DIR
    assert get_knowledge_path("TELECOM", "canonical") == KNOWLEDGE_DOCUMENTS_DIR


def test_get_path_maps_to_knowledge():
    from config.settings import KNOWLEDGE_DOCUMENTS_DIR

    assert get_path("nbr") == KNOWLEDGE_DOCUMENTS_DIR
    assert get_path("cost") == KNOWLEDGE_DOCUMENTS_DIR
    assert legacy_kb_subdir_to_discipline("nbrs") == ("geral", "raw")


def test_legacy_full_path_integration():
    from core.knowledge.resolver import legacy_kb_subdir_to_full_path

    assert legacy_kb_subdir_to_full_path("nbrs") == ("geral", "raw", "nbrs")
    assert legacy_kb_subdir_to_full_path("sinapi") == ("geral", "raw", "sinapi")
    assert legacy_kb_subdir_to_discipline("sinapi") == ("geral", "raw")
    assert legacy_kb_subdir_to_discipline("tdrs") == ("geral", "raw")


def test_discipline_slugs_complete():
    from core.knowledge.disciplines import DISCIPLINE_SLUGS

    assert "estruturas" in DISCIPLINE_SLUGS
    assert "telecom" in DISCIPLINE_SLUGS
    assert "infraestrutura" in DISCIPLINE_SLUGS
    assert "saneamento" in DISCIPLINE_SLUGS
    assert "geoprocessamento" in DISCIPLINE_SLUGS
    assert "topografia" in DISCIPLINE_SLUGS
    assert "meio_ambiente" in DISCIPLINE_SLUGS
    assert len(DISCIPLINE_SLUGS) == 16


def test_normalize_discipline_slug():
    assert normalize_discipline_slug("ESTRUTURAL") == "estruturas"
    assert normalize_discipline_slug("ORÇAMENTO") == "orcamento"
    assert normalize_discipline_slug("MEIO_AMBIENTE") == "meio_ambiente"
    assert normalize_discipline_slug("estrutural") == "estruturas"
    assert normalize_discipline_slug("") == "geral"


def test_route_knowledge_disabled_by_default():
    with patch("core.knowledge.router.settings.USE_DISCIPLINE_KNOWLEDGE_ROUTER", False):
        route = route_knowledge("dimensionar viga", discipline_hint="ESTRUTURAL")
    assert route.used_discipline_router is False
    assert route.discipline_slug == "estruturas"
    assert route.context_text == ""
    assert route.paths == []


def test_route_knowledge_enabled_collects_paths():
    with patch("core.knowledge.router.settings.USE_DISCIPLINE_KNOWLEDGE_ROUTER", True), patch(
        "core.knowledge.router.settings.USE_KNOWLEDGE_ROUTER", False
    ):
        route = route_knowledge("custo sinapi", discipline_hint="ORÇAMENTO")
    assert route.used_discipline_router is True
    assert route.discipline_slug == "orcamento"


def test_no_duplicate_dedup_keys():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        content = b"same content for dedup test"
        f.write(content)
        p1 = Path(f.name)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(content)
        p2 = Path(f.name)
    try:
        assert file_hash_dedup_key(p1) == file_hash_dedup_key(p2)
        assert file_dedup_key(p1) != file_dedup_key(p2) or p1.name == p2.name
    finally:
        p1.unlink(missing_ok=True)
        p2.unlink(missing_ok=True)


def test_rag_legacy_router_still_works():
    with patch("core.knowledge.knowledge_base_router.settings.USE_KNOWLEDGE_ROUTER", False):
        from core.knowledge.knowledge_base_router import enrich_route_with_knowledge

        route = {"input": "teste", "discipline": "ESTRUTURAL", "_use_rag": True}
        result = enrich_route_with_knowledge(route)
    assert result == route


def test_migration_dry_run_no_copy():
    from scripts.migrate_knowledge_by_discipline import migrate

    result = migrate(execute=False)
    assert result["dry_run"] is True
    assert "summary" in result


def test_indexer_always_includes_documents_paths():
    from core.knowledge.resolver import get_all_read_paths

    paths = get_all_read_paths("nbr")
    tiers = [t for _, t in paths]
    assert "documents" in tiers
    assert tiers[0] == "documents"


def test_indexer_legacy_only_when_excluded():
    from core.knowledge.resolver import get_all_read_paths

    paths = get_all_read_paths("nbr", include_discipline=False)
    tiers = [t for _, t in paths]
    assert "documents" not in tiers


if __name__ == "__main__":
    test_get_knowledge_path_resolution()
    test_get_path_maps_to_knowledge()
    test_legacy_full_path_integration()
    test_discipline_slugs_complete()
    test_normalize_discipline_slug()
    test_route_knowledge_disabled_by_default()
    test_route_knowledge_enabled_collects_paths()
    test_no_duplicate_dedup_keys()
    test_rag_legacy_router_still_works()
    test_migration_dry_run_no_copy()
    test_indexer_always_includes_documents_paths()
    test_indexer_legacy_only_when_excluded()
    print("OK — test_discipline_knowledge")
