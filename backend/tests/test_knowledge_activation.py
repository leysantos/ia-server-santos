"""Testes — Knowledge Activation Layer."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from core.knowledge.disciplines import resolve_slug_alias
from core.knowledge.ingestion import get_ingester
from core.knowledge.legacy_guard import assert_ingest_target
from core.knowledge.resolver import get_all_read_paths, get_knowledge_path


def test_resolve_slug_alias_formal():
    slug, was = resolve_slug_alias("estrutural")
    assert was is True
    assert slug == "estruturas"


def test_classify_nbr_to_estruturas():
    ingester = get_ingester()
    result = ingester.classify(Path("NBR-6118.pdf"))
    assert result.discipline_slug == "estruturas"
    assert result.content_type == "nbrs"
    assert result.confidence >= 0.9


def test_all_content_types_defined():
    from core.knowledge.content_types import KNOWLEDGE_CONTENT_TYPES

    expected = {"nbrs", "sinapi", "tcpo", "tdrs", "catalogos", "manuais", "projetos", "regional"}
    assert set(KNOWLEDGE_CONTENT_TYPES) == expected


def test_ingest_uses_knowledge_path():
    ingester = get_ingester()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 test")
        src = Path(f.name)
    try:
        with patch.object(settings, "USE_DISCIPLINE_INGESTION", True):
            record = ingester.ingest(
                src, discipline_hint="ESTRUTURAL", copy=True, force=True
            )
        target = Path(record["target"])
        assert "knowledge/raw/documents" in str(target).replace("\\", "/")
        assert Path(record["metadata_path"]).name.endswith(".knowledge.json")
        assert record["status"] == "copied"
        assert "document_id" in record
        target.unlink(missing_ok=True)
        sidecar = target.with_name(target.name + ".knowledge.json")
        sidecar.unlink(missing_ok=True)
    finally:
        src.unlink(missing_ok=True)


def test_ingest_blocks_data_dir_write():
    from config.settings import DATA_DIR

    try:
        assert_ingest_target(DATA_DIR / "learning_v2" / "profiles" / "ESTRUTURAL.json")
        assert False, "should raise"
    except PermissionError:
        pass


def test_documents_first_read_order():
    paths = get_all_read_paths(
        "nbr",
        include_discipline=True,
        discipline_first=True,
    )
    tiers = [t for _, t in paths]
    if "documents" in tiers and "legacy_readonly" in tiers:
        assert tiers.index("documents") < tiers.index("legacy_readonly")


def test_get_knowledge_path_integrated():
    from config.settings import KNOWLEDGE_DOCUMENTS_DIR

    p = get_knowledge_path("ESTRUTURAL", "raw")
    assert p == KNOWLEDGE_DOCUMENTS_DIR


def test_get_knowledge_path_ignores_content_type_param():
    p1 = get_knowledge_path("estrutural", "raw", "nbrs")
    p2 = get_knowledge_path("estrutural", "raw")
    assert p1 == p2
    assert "raw/documents" in str(p1).replace("\\", "/")


def test_enrich_unchanged_without_flags():
    from core.knowledge.knowledge_base_router import enrich_route_with_knowledge

    route = {"input": "teste", "discipline": "ESTRUTURAL", "_use_rag": True}
    with patch.object(settings, "USE_KNOWLEDGE_ROUTER", False), patch.object(
        settings, "USE_DISCIPLINE_KNOWLEDGE_ROUTER", False
    ):
        assert enrich_route_with_knowledge(route) == route


if __name__ == "__main__":
    test_resolve_slug_alias_formal()
    test_classify_nbr_to_estruturas()
    test_ingest_uses_knowledge_path()
    test_ingest_blocks_data_dir_write()
    test_documents_first_read_order()
    test_get_knowledge_path_integrated()
    test_get_knowledge_path_ignores_content_type_param()
    test_enrich_unchanged_without_flags()
    print("OK — test_knowledge_activation")
