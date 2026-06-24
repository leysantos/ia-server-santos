from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class KnowledgeOptionItem(BaseModel):
    value: str
    label: str


class DocumentTypePreset(BaseModel):
    id: str
    label: str
    content_type: str
    discipline: str
    register_price_base: bool = False
    register_budget_model: bool = False


class DocumentTypePresetCreateRequest(BaseModel):
    id: Optional[str] = Field(default=None, max_length=64, description="Identificador (opcional; gerado do nome)")
    label: str = Field(..., min_length=1, max_length=120)
    content_type: str = Field(..., min_length=1)
    discipline: str = Field(..., min_length=1)
    register_price_base: bool = False
    register_budget_model: bool = False


class DocumentTypePresetUpdateRequest(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=120)
    content_type: Optional[str] = None
    discipline: Optional[str] = None
    register_price_base: Optional[bool] = None
    register_budget_model: Optional[bool] = None


class DocumentTypePresetListResponse(BaseModel):
    presets: list[DocumentTypePreset]


class KnowledgeOptionsResponse(BaseModel):
    disciplines: list[KnowledgeOptionItem]
    content_types: list[KnowledgeOptionItem]
    bases: list[KnowledgeOptionItem]
    extensions: list[str]
    document_type_presets: list[DocumentTypePreset] = Field(default_factory=list)


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


class KnowledgeWebIngestRequest(BaseModel):
    page_url: str = Field(..., min_length=8, description="URL da página com links Baixar/Download")
    discipline: Optional[str] = Field(default=None, description="Disciplina (omitir = detectar por arquivo)")
    content_type: Optional[str] = Field(default=None, description="Tipo de conteúdo no catálogo (omitir = detectar)")
    description_prefix: Optional[str] = Field(default="", description="Prefixo opcional na descrição")
    max_files: int = Field(default=50, ge=1, le=300)
    force: bool = False
    auto_index: bool = True


class KnowledgeWebIngestFileLog(BaseModel):
    url: Optional[str] = None
    name: Optional[str] = None
    filename: Optional[str] = None
    status: Optional[str] = None
    ingest_status: Optional[str] = None
    document_id: Optional[str] = None
    error: Optional[str] = None


class KnowledgeWebIngestResponse(BaseModel):
    page_url: str
    pages_fetched: int = 1
    discovered: int
    downloaded: int
    ingested: int
    skipped: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
    files: list[dict[str, Any]] = Field(default_factory=list)
    indexing: Optional[dict[str, Any]] = None


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


class KnowledgePurgeGenericLegislationResponse(BaseModel):
    dry_run: bool
    count: Optional[int] = None
    requested: Optional[int] = None
    deleted: Optional[int] = None
    documents: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


class KnowledgeMaintenanceRequest(BaseModel):
    purge_orphans: bool = True
    dedupe_catalog: bool = True
    repair_norms: bool = True
    compact_faiss: bool = True
    index_pending: bool = True
    dry_run: bool = False


class KnowledgeMaintenanceResponse(BaseModel):
    purge_orphans: dict[str, Any] = Field(default_factory=dict)
    dedupe_catalog: dict[str, Any] = Field(default_factory=dict)
    repair_norms: dict[str, Any] = Field(default_factory=dict)
    compact_faiss: dict[str, Any] = Field(default_factory=dict)
    index_pending: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)


class KnowledgeNormStats(BaseModel):
    total: int = 0
    current_count: int = 0
    historical_count: int = 0
    without_year_count: int = 0
    nbr_count: int = 0
    nr_count: int = 0
    unknown_kind_count: int = 0
    unique_codes: int = 0
    multi_edition_codes: int = 0
    unique_editions: int = 0
    distinct_years: int = 0


class KnowledgeNbrCoverageStats(BaseModel):
    base: str = "nbr"
    catalog_files: int = 0
    files_on_disk: int = 0
    files_missing_disk: int = 0
    indexed_files: int = 0
    effective_indexed_files: int = 0
    dedup_only_files: int = 0
    not_indexed_files: int = 0
    catalog_codes: int = 0
    indexed_codes: int = 0
    not_indexed_codes: int = 0
    faiss_chunks: int = 0
    coverage_pct: float = 0.0
    file_coverage_pct: float = 0.0
    effective_file_coverage_pct: float = 0.0
    code_coverage_pct: float = 0.0
    healthy: bool = False
    sample_not_indexed: list[str] = Field(default_factory=list)
    sample_not_indexed_codes: list[str] = Field(default_factory=list)
    sample_extra_indexed: list[str] = Field(default_factory=list)


class KnowledgeStatsResponse(BaseModel):
    catalog_total: int
    catalog_log_entries: int = 0
    catalog_superseded: int = 0
    by_content_type: dict[str, int]
    index: dict[str, Any]
    norms: KnowledgeNormStats = Field(default_factory=KnowledgeNormStats)
    nbr_coverage: KnowledgeNbrCoverageStats = Field(default_factory=KnowledgeNbrCoverageStats)


class NormPackListItem(BaseModel):
    id: str
    label: str
    description: str
    tags: list[str] = Field(default_factory=list)
    item_count: int = 0
    critical_count: int = 0
    agent_slug: Optional[str] = None
    discipline: Optional[str] = None
    group: Optional[str] = None


class NormPackListResponse(BaseModel):
    legal_notice: str
    packs: list[NormPackListItem]


class NormPackItemStatus(BaseModel):
    nbr_code: str
    title: str
    discipline: str
    critical: bool = True
    status: str
    chunk_count: int = 0
    document_id: Optional[str] = None
    filename: Optional[str] = None
    file_path: Optional[str] = None
    legal_source: str
    upload_instruction: Optional[str] = None


class NormPackSummary(BaseModel):
    total: int
    indexed: int
    not_indexed: int
    missing: int
    critical_missing: int
    coverage_pct: float


class NormPackAnalyzeResponse(BaseModel):
    pack_id: str
    label: str
    description: str
    tags: list[str] = Field(default_factory=list)
    legal_notice: str
    summary: NormPackSummary
    items: list[NormPackItemStatus]


class NormPackIndexResult(BaseModel):
    nbr_code: str
    status: str
    chunks: int = 0
    error: Optional[str] = None


class NormPackIndexRequest(BaseModel):
    force: bool = False


class NormPackIndexResponse(BaseModel):
    pack_id: str
    force: bool
    indexed_chunks: int
    results: list[NormPackIndexResult]
    errors: list[dict[str, str]] = Field(default_factory=list)
    analysis_summary: NormPackSummary


class NormPackChunkPreview(BaseModel):
    chunk_index: int
    page: Optional[int] = None
    filename: Optional[str] = None
    edition_year: Optional[int] = None
    text: str
    char_count: int = 0


class NormPackNbrPreviewItem(BaseModel):
    nbr_code: str
    title: str
    filename: Optional[str] = None
    edition_year: Optional[int] = None
    legal_source: str = ""
    chunk_count: int = 0
    chunks: list[NormPackChunkPreview] = Field(default_factory=list)


class NormPackPreviewResponse(BaseModel):
    pack_id: str
    pack_label: str
    nbr_code_filter: Optional[str] = None
    indexed_count: int = 0
    items: list[NormPackNbrPreviewItem] = Field(default_factory=list)
    preview_notice: str = ""
