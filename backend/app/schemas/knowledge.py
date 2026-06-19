from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class KnowledgeOptionItem(BaseModel):
    value: str
    label: str


class KnowledgeOptionsResponse(BaseModel):
    disciplines: list[KnowledgeOptionItem]
    content_types: list[KnowledgeOptionItem]
    bases: list[KnowledgeOptionItem]
    extensions: list[str]


class KnowledgeClassificationResponse(BaseModel):
    discipline_slug: str
    content_type: str
    confidence: float
    source: str
    mapped_discipline: str


class KnowledgeIngestFileResult(BaseModel):
    filename: str
    status: str
    document_id: Optional[str] = None
    target: Optional[str] = None
    price_item_count: int = 0
    price_base_active: bool = False
    classification: Optional[KnowledgeClassificationResponse] = None
    reason: Optional[str] = None


class KnowledgeIngestError(BaseModel):
    filename: str
    error: str


class KnowledgeIndexSummary(BaseModel):
    base: Optional[str] = None
    indexed_files: int = 0
    indexed_chunks: int = 0
    skipped_files: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeIngestResponse(BaseModel):
    ingested: int
    skipped: int
    errors: list[KnowledgeIngestError]
    results: list[KnowledgeIngestFileResult]
    indexing: Optional[dict[str, Any]] = None


class KnowledgeIndexRequest(BaseModel):
    base: Optional[str] = Field(
        default=None,
        description="Base FAISS (nbr, sinapi, tcpo, …). Omitir para indexar todas.",
    )
    force: bool = False


class KnowledgeIndexResponse(BaseModel):
    bases: dict[str, Any] = Field(default_factory=dict)
    total_chunks: int = 0
    total_chunks_in_store: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeCatalogEntry(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    filename: str
    path: str
    discipline: list[str]
    content_type: str
    content_hash: Optional[str] = None
    catalog_ts: Optional[str] = None
    price_item_count: int = 0
    has_price_items: bool = False
    is_active_price_base: bool = False


class KnowledgeCatalogResponse(BaseModel):
    total: int
    log_entries: int = 0
    items: list[KnowledgeCatalogEntry]


class KnowledgeDocumentUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    content_type: Optional[str] = None
    discipline: Optional[str] = None


class KnowledgeDocumentUpdateResponse(BaseModel):
    updated: str
    name: str = ""
    description: str = ""
    content_type: str = ""
    discipline: list[str] = Field(default_factory=list)
    filename: str = ""


class KnowledgeDocumentDeleteResponse(BaseModel):
    deleted: str
    filename: str = ""
    was_active_price_base: bool = False
    catalog_entries_removed: int = 0
    faiss_chunks_removed: int = 0
    files_removed: list[str] = Field(default_factory=list)


class KnowledgeStatsResponse(BaseModel):
    catalog_total: int
    catalog_log_entries: int = 0
    by_content_type: dict[str, int]
    index: dict[str, Any]
