from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ResolveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    unit: Optional[str] = None
    region: Optional[str] = None
    source_priority: Optional[list[str]] = None
    limit: int = Field(default=10, ge=1, le=50)


class LoadProviderRequest(BaseModel):
    file_path: str


class BudgetBuildRequest(BaseModel):
    intent: dict[str, Any]
    source_priority: Optional[list[str]] = None


class BudgetGenerateRequest(BaseModel):
    text: str = Field(..., min_length=3)
    source_priority: Optional[list[str]] = None
    use_llm: bool = True
    obra_type: Optional[str] = Field(
        default=None,
        description="Tipo de obra para BDI: ED, RF, FIE, IE, OPMF, SEE, AG",
    )
    existing_session_id: Optional[str] = None


class BudgetSaveRequest(BaseModel):
    title: Optional[str] = None
    input_text: Optional[str] = None
    project_id: Optional[str] = None
    expected_version: Optional[int] = Field(
        default=None,
        description="Versão esperada do documento (lock otimista em updates)",
    )
    payload: dict[str, Any]


class BudgetRestoreRequest(BaseModel):
    payload: dict[str, Any]


class BdiObraTypeRequest(BaseModel):
    obra_type: str = Field(..., min_length=2, max_length=8)


class BdiTcuComponentsRequest(BaseModel):
    administracao_central: float = Field(0, ge=0, le=0.5)
    garantias_seguros: float = Field(0, ge=0, le=0.2)
    riscos: float = Field(0, ge=0, le=0.2)
    despesas_financeiras: float = Field(0, ge=0, le=0.2)
    lucro: float = Field(0, ge=0, le=0.5)
    tributos: float = Field(0, ge=0, le=0.5)


class BdiUpdateRequest(BaseModel):
    obra_type: Optional[str] = Field(None, min_length=2, max_length=8)
    source: Optional[str] = Field(None, pattern="^(seminf|edital|custom)$")
    profile_id: Optional[str] = None
    label: Optional[str] = None
    components_comd: Optional[BdiTcuComponentsRequest] = None
    components_semd: Optional[BdiTcuComponentsRequest] = None


class CellUpdateRequest(BaseModel):
    row_id: Optional[str] = None
    code: Optional[str] = None
    field: str = Field(..., pattern="^(quantity|unit_price|unit_cost|name|unit|calculation_note)$")
    value: Any


class ProjectUpdateRequest(BaseModel):
    projeto: Optional[str] = None
    nome_obra: Optional[str] = None
    objeto: Optional[str] = None
    local: Optional[str] = None
    endereco: Optional[str] = None
    empresa: Optional[str] = None
    orgao: Optional[str] = None
    responsavel_tecnico: Optional[str] = None
    base_preco: Optional[str] = None
    orcamento: Optional[str] = None
    data_ref: Optional[str] = None
    processo: Optional[str] = None
    price_bases: Optional[list[dict[str, Any]]] = None
    commercial_margin_pct: Optional[float] = Field(default=None, ge=0, le=100)
    commercial_client: Optional[str] = Field(default=None, max_length=200)


class EtapaCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class BudgetSkeletonSubEtapaInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class BudgetSkeletonEtapaInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sub_etapas: list[BudgetSkeletonSubEtapaInput] = Field(default_factory=list)


class BudgetSkeletonCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    obra_type: str = Field(default="RF", max_length=16)
    etapas: list[BudgetSkeletonEtapaInput] = Field(default_factory=list)


class BudgetSkeletonUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    obra_type: Optional[str] = Field(default=None, max_length=16)
    etapas: Optional[list[BudgetSkeletonEtapaInput]] = None


class SubEtapaCreateRequest(BaseModel):
    parent_code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)


class EtapaUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class MemoryGenerateRequest(BaseModel):
    group_code: Optional[str] = Field(default=None, description="Código etapa/sub-etapa; vazio = obra inteira")
    use_llm: bool = False
    llm_model: Optional[str] = Field(
        default=None,
        description='Modelo Ollama. Use "auto" ou omita para roteamento automático.',
    )


class ScheduleSettingsRequest(BaseModel):
    project_start: str = Field(..., min_length=8, max_length=10, description="Data de início (ISO YYYY-MM-DD)")


class ScheduleTaskUpdateRequest(BaseModel):
    duration_days: Optional[int] = Field(default=None, ge=1, le=3650)
    manual_start: Optional[str] = Field(default=None, description="Início manual ISO YYYY-MM-DD")


class ScheduleLinkRequest(BaseModel):
    predecessor_id: str = Field(..., min_length=1)
    successor_id: str = Field(..., min_length=1)
    link_type: str = Field(default="FS", pattern="^(FS|SS|FF|SF)$")
    lag_days: int = Field(default=0, ge=0, le=365)


class ScheduleComposeRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=4000)
    use_llm: bool = True
    replace_links: bool = Field(
        default=False,
        description="Se true, remove todos os vínculos antes de aplicar o plano da IA",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description='Modelo Ollama. Use "auto" ou omita para roteamento automático.',
    )


class TechSpecComposeRequest(BaseModel):
    prompt: Optional[str] = Field(
        default=None,
        max_length=8000,
        description="Instruções para gerar ou editar o documento.",
    )
    mode: str = Field(
        default="generate",
        pattern="^(generate|edit)$",
        description="generate = criar do orçamento; edit = alterar documento existente via prompt.",
    )
    use_llm: bool = True
    llm_model: Optional[str] = Field(default=None, description="Modelo Ollama ou auto.")


class TechSpecUpdateRequest(BaseModel):
    title: Optional[str] = None
    markdown: Optional[str] = None
    html_content: Optional[str] = None
    formatting: Optional[dict[str, Any]] = None


class ComposeEtapaRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=4000)
    source_priority: Optional[list[str]] = None
    default_quantity: Optional[float] = Field(
        default=None,
        ge=0,
        description="Quantidade aplicada a todos os termos sem quantidade individual",
    )
    replace_existing: bool = Field(
        default=False,
        description="Se true, remove serviços atuais do grupo antes de compor",
    )


class ReplaceServiceRequest(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    source: Optional[str] = "sinapi"
    query: Optional[str] = None
    source_priority: Optional[list[str]] = None


class ApplyGroupQuantityRequest(BaseModel):
    quantity: float = Field(..., ge=0)
    include_subgroups: bool = Field(
        default=True,
        description="Se true, aplica também aos serviços das sub-etapas",
    )


class AddServiceRequest(BaseModel):
    etapa_code: str = Field(..., min_length=1)
    code: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    source: Optional[str] = "sinapi"
    quantity: float = Field(default=1.0, ge=0)
    query: Optional[str] = None
    source_priority: Optional[list[str]] = None


class SearchPriceRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=15, ge=1, le=50)
    source_priority: Optional[list[str]] = None
    session_id: Optional[str] = None

class PriceSyncRequest(BaseModel):
    uf: str = Field(default="SP", min_length=2, max_length=2)
    year: Optional[int] = None
    month: Optional[int] = Field(default=None, ge=1, le=12)
    local_file: Optional[str] = None
    index_faiss: bool = True
    reload_providers: bool = True
    set_active: bool = False
    include_open: bool = Field(
        default=True,
        description="Importar composições abertas (analítico/CPU)",
    )
    include_closed: bool = Field(
        default=True,
        description="Importar composições fechadas (sintéticas)",
    )
    include_insumos: bool = Field(default=True, description="Importar catálogo de insumos")
    download_all_regions: bool = Field(
        default=False,
        description="SICRO: baixar todas as UFs publicadas no portal DNIT",
    )
    skip_existing_ufs: bool = Field(
        default=False,
        description="SICRO (lote): pular UFs já importadas para o mesmo ano/mês",
    )
    package_only: bool = Field(
        default=False,
        description="ORSE: baixar apenas pacote .ORSE da CEHOP (sem importar price_bank)",
    )
    portal_sync: bool = Field(
        default=False,
        description="ORSE: importar via portal público CEHOP (sem ORSE 2 / Excel)",
    )

class PriceBankActiveRequest(BaseModel):
    reference: str = Field(..., min_length=3)

class PriceSourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=40)
    label: str = Field(..., min_length=2, max_length=80)
    download_url: str = Field(default="")


class PriceSourceConfigRequest(BaseModel):
    download_url: str | None = None
    label: str | None = Field(default=None, max_length=80)

class SeminfRefreshPricesRequest(BaseModel):
    reference: str = Field(..., min_length=3)
    sinapi_reference: str = Field(..., min_length=3)
    uf: str = Field(default="AM", min_length=2, max_length=2)
    set_active: bool = False

class BudgetRevisionCreateRequest(BaseModel):
    revision_label: Optional[str] = Field(None, max_length=80)

class ExportBrandingUpdateRequest(BaseModel):
    header_title: str | None = None
    header_line1: str | None = None
    header_line2: str | None = None
    header_line3: str | None = None
    footer_line1: str | None = None
    footer_line2: str | None = None
    show_logo: bool | None = None
    show_brasao: bool | None = None
