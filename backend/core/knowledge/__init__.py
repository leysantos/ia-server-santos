"""Knowledge Layer — roteamento multi-base (NBR, SINAPI, TCPO, TDR, catálogos)."""

from core.knowledge.constants import IMMUTABLE_KNOWLEDGE_BASES, KNOWLEDGE_PATHS
from core.knowledge.domain_detector import detect_domain
from core.knowledge.knowledge_base_router import (
    KnowledgeBaseRouter,
    enrich_route_with_knowledge,
    get_knowledge_router,
)
from core.knowledge.knowledge_indexer import KnowledgeIndexer
from core.knowledge.disciplines import DISCIPLINE_SLUGS, DISCIPLINE_TO_SLUG, slug_for_discipline
from core.knowledge.ingestion import DisciplineIngester, get_ingester
from core.knowledge.resolver import get_knowledge_path, get_path, is_legacy_path, normalize_base_key
from core.knowledge.router import route_knowledge

__all__ = [
    "IMMUTABLE_KNOWLEDGE_BASES",
    "KNOWLEDGE_PATHS",
    "KnowledgeBaseRouter",
    "KnowledgeIndexer",
    "DisciplineIngester",
    "DISCIPLINE_SLUGS",
    "DISCIPLINE_TO_SLUG",
    "detect_domain",
    "enrich_route_with_knowledge",
    "get_ingester",
    "get_knowledge_router",
    "get_knowledge_path",
    "get_path",
    "is_legacy_path",
    "normalize_base_key",
    "route_knowledge",
    "slug_for_discipline",
]
