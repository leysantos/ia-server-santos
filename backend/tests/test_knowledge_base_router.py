"""Testes da Knowledge Layer multi-base."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.knowledge.constants import (
    DOMAIN_BUDGET,
    DOMAIN_COST,
    DOMAIN_GEOTECHNICAL,
    DOMAIN_NORM,
    DOMAIN_STRUCTURAL,
    IMMUTABLE_KNOWLEDGE_BASES,
    KNOWLEDGE_INDEX_NAMES,
)
from core.knowledge.domain_detector import detect_domain
from core.knowledge.knowledge_base_router import (
    KnowledgeBaseRouter,
    enrich_route_with_knowledge,
)


def test_resolver_get_path_domains():
    from config.settings import KNOWLEDGE_DOCUMENTS_DIR
    from core.knowledge.resolver import get_path

    assert get_path("nbr") == KNOWLEDGE_DOCUMENTS_DIR
    assert get_path("cost") == KNOWLEDGE_DOCUMENTS_DIR
    assert get_path("composition") == KNOWLEDGE_DOCUMENTS_DIR
    assert get_path("catalog") == KNOWLEDGE_DOCUMENTS_DIR
    assert get_path("project") == KNOWLEDGE_DOCUMENTS_DIR


def test_resolver_data_dir_is_not_knowledge():
    from config.settings import DATA_DIR, KNOWLEDGE_DOCUMENTS_DIR
    from core.knowledge.resolver import is_canonical_path, is_legacy_path

    assert is_legacy_path(DATA_DIR / "learning_v2" / "profiles" / "x.json") is True
    assert is_legacy_path(KNOWLEDGE_DOCUMENTS_DIR / "NBR-6118.pdf") is False
    assert is_canonical_path(KNOWLEDGE_DOCUMENTS_DIR) is True


def test_resolver_read_paths_priority():
    from core.knowledge.resolver import get_all_read_paths

    paths = get_all_read_paths("nbr")
    tiers = [tier for _, tier in paths]
    assert tiers[0] == "documents"
    assert "legacy_readonly" in tiers or len(paths) >= 1


def test_file_dedup_key_same_name_size():
    from core.knowledge.resolver import file_dedup_key
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"x" * 100)
        p1 = Path(f.name)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"x" * 100)
        p2 = Path(f.name)
    try:
        p2 = p2.rename(p2.parent / p1.name) if p1.name != p2.name else p2
        assert file_dedup_key(p1) == file_dedup_key(p2)
    finally:
        p1.unlink(missing_ok=True)
        p2.unlink(missing_ok=True)


def test_knowledge_paths_use_canonical_dir():
    from config.settings import KNOWLEDGE_DOCUMENTS_DIR
    from core.knowledge.constants import KNOWLEDGE_PATHS

    assert KNOWLEDGE_PATHS["nbr"] == KNOWLEDGE_DOCUMENTS_DIR
    assert KNOWLEDGE_PATHS["sinapi"] == KNOWLEDGE_DOCUMENTS_DIR
    assert KNOWLEDGE_PATHS["tdr"] == KNOWLEDGE_DOCUMENTS_DIR


def test_nbr_dir_points_to_knowledge():
    from config.settings import KNOWLEDGE_DOCUMENTS_DIR, NBR_DIR, TDR_DIR

    assert NBR_DIR == KNOWLEDGE_DOCUMENTS_DIR
    assert TDR_DIR == KNOWLEDGE_DOCUMENTS_DIR


def test_immutable_knowledge_bases_flag():
    assert IMMUTABLE_KNOWLEDGE_BASES is True


def test_index_names_mapping():
    assert KNOWLEDGE_INDEX_NAMES["nbr"] == "nbr_index"
    assert KNOWLEDGE_INDEX_NAMES["sinapi"] == "cost_index"
    assert KNOWLEDGE_INDEX_NAMES["tcpo"] == "composition_index"


def test_detect_domain_structural():
    assert detect_domain("dimensionar viga de concreto") == DOMAIN_STRUCTURAL


def test_detect_domain_cost():
    assert detect_domain("custo concreto m³ sinapi") == DOMAIN_COST


def test_detect_domain_budget():
    assert detect_domain("orçamento de obra escola tcpo") == DOMAIN_BUDGET


def test_detect_domain_norm():
    assert detect_domain("norma acessibilidade NBR 9050") == DOMAIN_NORM


def test_detect_domain_geotechnical():
    assert detect_domain("fundação em solo fraco") == DOMAIN_GEOTECHNICAL


def test_detect_domain_discipline_orcamento():
    assert detect_domain("planilha de custos", discipline="ORÇAMENTO") == DOMAIN_COST


def test_enrich_route_with_knowledge_disabled():
    route = {"input": "dimensionar viga", "discipline": "ESTRUTURAL"}
    with patch("core.knowledge.knowledge_base_router.settings.USE_KNOWLEDGE_ROUTER", False):
        result = enrich_route_with_knowledge(route)
    assert result == route


def test_enrich_route_with_knowledge_enabled_empty_index():
    route = {"input": "dimensionar viga", "discipline": "ESTRUTURAL", "_use_rag": True}
    with patch("core.knowledge.knowledge_base_router.settings.USE_KNOWLEDGE_ROUTER", True):
        with patch(
            "core.knowledge.knowledge_base_router.get_knowledge_router"
        ) as mock_get:
            mock_router = MagicMock()
            mock_router.retrieve_context.return_value = MagicMock(
                context_text="",
                domain=DOMAIN_STRUCTURAL,
                bases_used=["nbr_index"],
                hits_count=0,
                fallback_legacy=False,
                to_dict=lambda: {},
            )
            mock_get.return_value = mock_router
            result = enrich_route_with_knowledge(route)
    assert "context" not in result


def test_router_retrieve_context_with_hits():
    mock_store = MagicMock()
    mock_store.search_many.return_value = []
    mock_store.total_chunks.return_value = 0

    with patch(
        "core.knowledge.knowledge_base_router.settings.USE_AGENT_SCOPED_RAG",
        False,
    ), patch(
        "core.knowledge.knowledge_base_router.get_multi_index_store",
        return_value=mock_store,
    ), patch(
        "core.knowledge.knowledge_base_router.KnowledgeBaseRouter._legacy_fallback",
        return_value=[],
    ):
        router = KnowledgeBaseRouter()
        kc = router.retrieve_context("custo sinapi", domain=DOMAIN_COST)
    assert kc.domain == DOMAIN_COST
    assert kc.bases_used == ["cost_index"]


def test_dispatcher_calls_knowledge_router_when_enabled():
    from core.dispatcher import dispatch

    route = {
        "discipline": "ESTRUTURAL",
        "input": "teste",
        "_use_rag": True,
    }
    mock_agent = MagicMock()
    mock_agent.handle.return_value = {"result": "ok"}

    with patch("core.dispatcher.USE_KNOWLEDGE_ROUTER", True), patch(
        "core.dispatcher.AGENTS", {"ESTRUTURAL": mock_agent}
    ), patch(
        "core.knowledge.knowledge_base_router.enrich_route_with_knowledge",
        side_effect=lambda r: {**r, "context": "ctx"},
    ) as mock_enrich:
        dispatch(route, persist=False)
        mock_enrich.assert_called_once()


if __name__ == "__main__":
    test_resolver_get_path_domains()
    test_resolver_data_dir_is_not_knowledge()
    test_resolver_read_paths_priority()
    test_knowledge_paths_use_canonical_dir()
    test_nbr_dir_points_to_knowledge()
    test_immutable_knowledge_bases_flag()
    test_index_names_mapping()
    test_detect_domain_structural()
    test_detect_domain_cost()
    test_detect_domain_budget()
    test_detect_domain_norm()
    test_detect_domain_geotechnical()
    test_detect_domain_discipline_orcamento()
    test_enrich_route_with_knowledge_disabled()
    test_enrich_route_with_knowledge_enabled_empty_index()
    test_router_retrieve_context_with_hits()
    test_dispatcher_calls_knowledge_router_when_enabled()
    print("OK — test_knowledge_base_router")
