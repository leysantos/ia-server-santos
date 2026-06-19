"""Verifica alinhamento knowledge/ ↔ agents/ ↔ agent_registry."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import KNOWLEDGE_DISCIPLINE_DIR
from core.agent_registry import DISCIPLINE_TO_AGENT
from core.agents.base_agent_intelligent import DISCIPLINE_NBRS
from core.knowledge.disciplines import DISCIPLINE_SLUGS, DISCIPLINE_TO_SLUG, slug_for_discipline


def _agent_modules() -> set[str]:
    agents_dir = Path(__file__).resolve().parent.parent / "agents"
    return {
        p.stem
        for p in agents_dir.glob("*.py")
        if p.stem not in ("base_agent", "chat", "__init__")
    }


def test_discipline_slugs_match_agent_registry():
    expected = {name.removesuffix("_agent") for name in DISCIPLINE_TO_AGENT.values()}
    assert set(DISCIPLINE_SLUGS) == expected


def test_every_engineering_agent_has_slug():
    for discipline in DISCIPLINE_NBRS:
        slug = DISCIPLINE_TO_SLUG[discipline]
        assert slug in DISCIPLINE_SLUGS, f"{discipline} → {slug}"


def test_agent_module_names_have_knowledge_slug():
    modules = _agent_modules()
    for module in modules:
        slug = slug_for_discipline(module)
        assert slug in DISCIPLINE_SLUGS, f"agents/{module}.py sem slug: {slug}"


def test_documents_dir_is_flat_storage():
    from core.knowledge.resolver import get_documents_dir

    assert get_documents_dir().name == "documents"
    assert get_documents_dir().parent.name == "raw"


def test_estrutural_resolves_to_estruturas():
    assert slug_for_discipline("ESTRUTURAL") == "estruturas"
    assert slug_for_discipline("estrutural") == "estruturas"


def test_all_registry_disciplines():
    assert len(DISCIPLINE_TO_SLUG) == len(DISCIPLINE_TO_AGENT)
    assert "ESTRUTURAL" in DISCIPLINE_TO_SLUG
    assert DISCIPLINE_TO_SLUG["ESTRUTURAL"] == "estruturas"
    assert DISCIPLINE_TO_SLUG["TELECOM"] == "telecom"
    assert DISCIPLINE_TO_SLUG["MEIO_AMBIENTE"] == "meio_ambiente"
    assert DISCIPLINE_TO_SLUG["GEOPROCESSAMENTO"] == "geoprocessamento"
    assert DISCIPLINE_TO_SLUG["TOPOGRAFIA"] == "topografia"
    assert DISCIPLINE_TO_SLUG["INFRAESTRUTURA"] == "infraestrutura"
    assert DISCIPLINE_TO_SLUG["SANEAMENTO"] == "saneamento"


def test_sixteen_discipline_folders():
    # 15 engenharia + GERAL (CHAT excluído do registry de conhecimento)
    assert len(DISCIPLINE_SLUGS) == 16


def test_no_deprecated_folders_on_disk():
    from core.knowledge.disciplines import DEPRECATED_SLUG_DIRS

    for name in DEPRECATED_SLUG_DIRS:
        assert not (KNOWLEDGE_DISCIPLINE_DIR / name).exists(), f"deprecated folder: {name}"


def test_scaffold_specs_flat_documents():
    from core.knowledge.resolver import STORAGE_LAYER, discipline_scaffold_specs

    specs = discipline_scaffold_specs()
    assert specs == {"documents": frozenset({STORAGE_LAYER})}


if __name__ == "__main__":
    test_discipline_slugs_match_agent_registry()
    test_every_engineering_agent_has_slug()
    test_agent_module_names_have_knowledge_slug()
    test_documents_dir_is_flat_storage()
    test_estrutural_resolves_to_estruturas()
    test_all_registry_disciplines()
    test_sixteen_discipline_folders()
    test_no_deprecated_folders_on_disk()
    test_scaffold_specs_flat_documents()
    print("OK — test_knowledge_agents_alignment")
