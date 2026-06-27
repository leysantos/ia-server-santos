export interface ChatRequest {
  text: string;
  use_rag?: boolean;
  persist?: boolean;
  conversation_id?: string;
  project_id?: string;
  llm_model?: string | null;
}

export interface ChatResponse {
  input: string;
  discipline?: string;
  agent?: string;
  result?: string;
  response?: string;
  extra?: Record<string, unknown>;
  conversation_id?: string;
  route?: {
    discipline?: string;
    agent?: string;
    mode?: string;
  };
  intent?: Record<string, unknown>;
  segments?: ChatResponse[];
  error?: boolean;
}

export type ChatStreamEventType =
  | "status"
  | "intent"
  | "token"
  | "segment_done"
  | "done"
  | "error";

export interface ChatStreamEvent {
  type: ChatStreamEventType | string;
  data: Record<string, unknown>;
}

export interface OrchestrateRequest {
  text: string;
  use_rag?: boolean;
  persist?: boolean;
  llm_model?: string | null;
}

export interface OrchestrateResponse {
  input: string;
  disciplines: string[];
  results: Record<string, AgentResult>;
  final_report: string;
  synthesis: {
    technical_summary: string;
    general_conclusion: string;
  };
  conversation_id?: string;
  orchestrator_log_id?: string;
}

export interface CopilotRequest {
  text: string;
  use_rag?: boolean;
  persist?: boolean;
}

export interface CopilotResponse {
  input: string;
  intent: string;
  intent_confidence: number;
  matched_categories: string[];
  plan: Record<string, unknown>[];
  disciplines: string[];
  result: Record<string, unknown>;
  evaluation: Record<string, unknown>;
  evaluation_v2?: Record<string, unknown>;
  context_graph?: Record<string, unknown>;
  conversation_id?: string;
}

export interface AedRequest {
  text: string;
  use_rag?: boolean;
  persist?: boolean;
}

export interface AedResponse {
  input: string;
  conversation_id?: string;
  understanding: Record<string, unknown>;
  structural_selection?: Record<string, unknown>;
  designs: Record<string, unknown>[];
  simulations: Record<string, unknown>[];
  comparison: Record<string, unknown>;
  selection: Record<string, unknown>;
  report: Record<string, unknown>;
  use_rag?: boolean;
  aed_run_id?: string;
}

export interface AgentResult {
  agent?: string;
  discipline?: string;
  input?: string;
  result?: string;
  response?: string;
  extra?: Record<string, unknown>;
  error?: boolean;
}

export interface HistoryResponse {
  total: number;
  items: HistoryItem[];
}

export interface HistoryItem {
  id: string;
  title?: string;
  input_text: string;
  mode: "single" | "multi";
  message_count?: number;
  project_id?: string | null;
  created_at?: string;
  updated_at?: string;
  messages?: ConversationMessageItem[];
  orchestrator_logs?: OrchestratorLogItem[];
  agent_runs?: AgentRunItem[];
}

export interface ConversationMessageItem {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  meta?: Record<string, unknown>;
  created_at?: string;
}

export interface ConversationSummary {
  id: string;
  title?: string;
  input_text: string;
  mode: string;
  message_count: number;
  project_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ConversationListResponse {
  total: number;
  items: ConversationSummary[];
}

export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessageItem[];
}

export interface ProjectSummary {
  id: string;
  name: string;
  description?: string | null;
  codigo?: string | null;
  cliente?: string | null;
  responsavel?: string | null;
  disciplina?: string | null;
  status?: string;
  versao_atual?: string;
  workflow_initialized?: boolean;
  empresa_id?: string | null;
  created_at?: string;
  updated_at?: string;
  conversation_count: number;
  file_count: number;
}

export interface ProjectFileItem {
  id: string;
  project_id: string;
  filename: string;
  storage_path: string;
  content_type?: string | null;
  size_bytes?: number | null;
  created_at?: string;
}

export interface ProjectDetail extends ProjectSummary {
  conversations: ConversationSummary[];
  files: ProjectFileItem[];
}

export interface ProjectListResponse {
  total: number;
  items: ProjectSummary[];
}

export interface ProjectFormatItem {
  ext: string;
  label: string;
}

export interface ProjectFormatsResponse {
  formats: ProjectFormatItem[];
  accept: string;
}

export interface WorkspaceSearchResponse {
  query: string;
  total: number;
  projects: ProjectSummary[];
  conversations: ConversationSummary[];
}

export interface WorkflowFolderItem {
  id: string;
  nome: string;
  path: string;
  disciplina?: string | null;
  sort_order: number;
}

export interface WorkflowDrawingItem {
  id: string;
  classificacao?: string | null;
  escala?: string | null;
  disciplina?: string | null;
  project_file_id?: string | null;
  filename?: string | null;
  tipo_arquivo?: "prancha" | "documento" | "cad" | "bim" | string;
  subtipo?: string | null;
}

export interface WorkflowInventoryItem {
  file_id: string;
  filename: string;
  tipo_arquivo: string;
  subtipo: string;
  pipeline: string;
  processed: boolean;
}

export interface WorkflowSummary {
  total_arquivos: number;
  arquivos_suportados: number;
  pranchas: number;
  documentos: number;
  pranchas_geradas: number;
  revisoes: number;
  entregas: number;
}

export interface WorkflowSheetItem {
  id: string;
  numero_prancha?: string | null;
  codigo_desenho?: string | null;
  escala?: string | null;
  disciplina?: string | null;
  status: string;
}

export interface WorkflowRevisionItem {
  id: string;
  codigo: string;
  autor?: string | null;
  descricao?: string | null;
  created_at?: string | null;
}

export interface WorkflowVersionItem {
  id: string;
  branch: string;
  tag?: string | null;
  commit_hash: string;
  mensagem?: string | null;
  created_at?: string | null;
}

export interface WorkflowEventItem {
  id: string;
  event_type: string;
  payload?: Record<string, unknown> | null;
  actor?: string | null;
  created_at?: string | null;
}

export interface WorkflowProjectState {
  project: {
    id: string;
    name: string;
    codigo?: string | null;
    cliente?: string | null;
    responsavel?: string | null;
    disciplina?: string | null;
    status: string;
    versao_atual: string;
    workflow_initialized: boolean;
    empresa_id?: string | null;
  };
  folders: WorkflowFolderItem[];
  summary?: WorkflowSummary;
  inventory?: WorkflowInventoryItem[];
  drawings: WorkflowDrawingItem[];
  sheets: WorkflowSheetItem[];
  revisions: WorkflowRevisionItem[];
  versions: WorkflowVersionItem[];
  events: WorkflowEventItem[];
  deliveries?: WorkflowDeliveryItem[];
  jobs?: WorkflowJobItem[];
}

export interface WorkflowDashboardResponse {
  projetos_ativos: number;
  arquivos_processados: number;
  pranchas_geradas: number;
  revisoes_registradas: number;
  publicacoes_recentes: number;
  eventos_recentes: WorkflowEventItem[];
}

export interface WorkflowJobItem {
  id: string;
  project_id: string;
  job_type: string;
  status: string;
  celery_task_id?: string | null;
  file_id?: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface WorkflowDeliveryItem {
  id: string;
  status: string;
  package_path?: string | null;
  pdf_uri?: string | null;
  pdf_key?: string | null;
  pdf_download_url?: string | null;
  zip_uri?: string | null;
  zip_key?: string | null;
  zip_download_url?: string | null;
  storage_backend?: string | null;
  created_at?: string | null;
}

export interface WorkflowProcessResponse {
  mode?: string;
  job_id?: string;
  task_id?: string;
  status?: string;
  processed?: number;
  skipped?: number;
  pranchas?: number;
  documentos?: number;
}

export interface SheetTemplateItem {
  id: string;
  nome: string;
  formato: string;
  orientacao: string;
  disciplina?: string | null;
  company_id?: string | null;
}

export interface DeliveryPackageSummary {
  id: string;
  titulo: string;
  status: string;
  codigo_emissao: string;
  created_at?: string | null;
  published_at?: string | null;
}

export interface DeliveryPackageItem {
  id: string;
  project_file_id: string;
  filename?: string | null;
  selected: boolean;
  role: string;
  disciplina?: string | null;
  disciplina_codigo?: string | null;
  folha_numero?: number | null;
  tipo_desenho?: string | null;
  titulo?: string | null;
  codigo_sugerido?: string | null;
  codigo_aprovado?: string | null;
  arquivo_final?: string | null;
  formato?: string | null;
  escala?: string | null;
  pasta_destino?: string | null;
  revisao_documento?: string | null;
  sort_order: number;
  status: string;
  analysis?: Record<string, unknown> | null;
}

export interface DeliveryPackageDetail {
  package: {
    id: string;
    project_id: string;
    status: string;
    titulo: string;
    codigo_emissao: string;
    formato_padrao: string;
    orientacao_padrao: string;
    template_id?: string | null;
    stamp_id?: string | null;
    observacoes?: string | null;
    package_path?: string | null;
    published_delivery_id?: string | null;
    created_at?: string | null;
    published_at?: string | null;
  };
  items: DeliveryPackageItem[];
  available_files: { id: string; filename: string; created_at?: string | null }[];
  structure_preview: Record<string, string[]>;
  norm_gaps?: ProjectNormGaps | null;
}

export interface ProjectNormGapItem {
  nbr_code: string;
  title: string;
  status: "missing" | "not_indexed" | string;
  critical: boolean;
  pack_id: string;
  pack_label: string;
  discipline: string;
  action: string;
}

export interface ProjectNormGaps {
  has_critical_gaps: boolean;
  has_any_gaps: boolean;
  critical_missing_count: number;
  critical_not_indexed_count: number;
  missing_purchase_count: number;
  not_indexed_count: number;
  pending_total: number;
  summary_message: string;
  settings_path: string;
  pack_ids: string[];
  pending_items: ProjectNormGapItem[];
  packs_checked?: { pack_id: string; pack_label: string; coverage_pct: number; critical_missing: number }[];
}

export interface DeliveryPublishResponse {
  status: string;
  delivery_id?: string;
  package_id?: string;
  sheets_created?: number;
  revisions_created?: number;
  total_items?: number;
  zip?: { key?: string; uri?: string; backend?: string };
  grd?: { key?: string; uri?: string; backend?: string };
  package?: DeliveryPackageDetail["package"];
}

export interface OrchestratorLogItem {
  id: string;
  disciplines?: string[];
  final_report?: string;
  synthesis?: Record<string, string>;
  use_rag?: boolean;
  agent_count?: number;
  created_at?: string;
}

export interface AgentRunItem {
  id: string;
  discipline?: string;
  agent_name?: string;
  result_text?: string;
  had_context?: boolean;
  created_at?: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  rag_version: number;
  rag_indexed_chunks: number;
  ollama: string;
  installed_models?: string[];
  models?: {
    chat: string;
    engineering: string;
    fallback: string;
    embed: string;
    installed_llm?: string;
    router_enabled?: string;
    evaluation_enabled?: string;
  };
}

export interface ModelsStatusResponse {
  router_enabled: boolean;
  evaluation_enabled?: boolean;
  model_map?: Record<string, string>;
  installed_models?: string[];
  ollama?: string;
}

export interface SystemBenchmarkMetric {
  percent?: number | null;
  cores?: number;
  used_gb?: number;
  total_gb?: number;
  available?: boolean;
  memory_percent?: number | null;
  memory_used_mb?: number;
  memory_total_mb?: number;
  used_mb?: number;
  total_mb?: number;
}

export interface SystemBenchmarkResponse {
  available: boolean;
  error?: string;
  timestamp?: number;
  cpu?: SystemBenchmarkMetric;
  memory?: SystemBenchmarkMetric;
  gpu?: SystemBenchmarkMetric;
  vram?: SystemBenchmarkMetric;
}

export interface CompanyProfile {
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  endereco: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
  telefone: string;
  email: string;
  site: string;
  responsavel_tecnico: string;
  rt_profissao: string;
  rt_crea: string;
  rt_email: string;
  rt_telefone: string;
  has_logo?: boolean;
  has_brasao?: boolean;
}

export interface ExportBrandingConfig {
  header_title?: string;
  header_line1?: string;
  header_line2?: string;
  header_line3?: string;
  footer_line1?: string;
  footer_line2?: string;
  show_logo?: boolean;
  show_brasao?: boolean;
  has_logo?: boolean;
  has_brasao?: boolean;
}

export type UserRole = string;

export interface ModulePermission {
  hidden: boolean;
  blocked: boolean;
}

export type ModulePermissionsMap = Record<string, ModulePermission>;

export interface UserRoleDefinition {
  slug: string;
  label: string;
  module_permissions: ModulePermissionsMap;
  is_system: boolean;
  created_at?: string;
}

export interface AuthUser {
  id: string;
  username: string;
  email: string | null;
  full_name: string | null;
  role: UserRole;
  role_label?: string;
  module_permissions?: ModulePermissionsMap;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AuthStatusResponse {
  auth_enabled: boolean;
  token_expire_minutes?: number;
}

export interface AuthMeResponse {
  auth_enabled: boolean;
  user: AuthUser | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface UsersListResponse {
  users: AuthUser[];
}

export interface UserRolesListResponse {
  roles: UserRoleDefinition[];
}

export interface SystemModulesResponse {
  modules: { id: string; label: string; description: string }[];
}

export interface InternalNetworkConfig {
  enabled: boolean;
  host_ip: string;
  api_port: number;
  frontend_port: number;
  api_base_url: string;
  frontend_url: string;
  allowed_cidrs: string[];
  bind_api_all_interfaces: boolean;
  notes: string;
}

export interface CloudflareAccessConfig {
  enabled: boolean;
  tunnel_name: string;
  tunnel_id: string;
  tunnel_token?: string;
  tunnel_token_configured?: boolean;
  tunnel_token_hint?: string;
  account_id: string;
  zone_id: string;
  public_hostname: string;
  public_api_url: string;
  public_frontend_url: string;
  access_application_name: string;
  access_policy: string;
  warp_required: boolean;
  notes: string;
}

export interface QuickTunnelStatus {
  cloudflared_installed: boolean;
  running: boolean;
  status: "running" | "stopped" | string;
  api_url: string;
  frontend_url: string;
  api_pid?: number | null;
  frontend_pid?: number | null;
  started_at?: string | null;
  restart_hint?: string;
  env_hint?: string;
  message?: string;
}

export interface NetworkAccessConfig {
  internal: InternalNetworkConfig;
  cloudflare: CloudflareAccessConfig;
  cors_extra_origins: string[];
  suggested_cors_origins: string[];
  env_cors_origins?: string[];
  auth_enabled?: boolean;
  effective_access_mode?: string;
  quick_tunnel?: QuickTunnelStatus;
  restart_hint?: string;
  saved?: boolean;
}

export interface KnowledgeOptionItem {
  value: string;
  label: string;
}

export interface DocumentTypePreset {
  id: string;
  label: string;
  content_type: string;
  discipline: string;
  register_price_base: boolean;
  register_budget_model: boolean;
}

export interface KnowledgeOptionsResponse {
  disciplines: KnowledgeOptionItem[];
  content_types: KnowledgeOptionItem[];
  bases: KnowledgeOptionItem[];
  extensions: string[];
  document_type_presets?: DocumentTypePreset[];
}

export interface KnowledgeIngestFileResult {
  filename: string;
  status: string;
  document_id?: string;
  target?: string;
  classification?: {
    discipline_slug: string;
    content_type: string;
    confidence: number;
    source: string;
    mapped_discipline: string;
  };
  reason?: string;
  price_item_count?: number;
  price_base_active?: boolean;
  budget_model_indexed?: number;
  service_count?: number;
  saved_as?: string;
  storage_renamed?: boolean;
}

export interface KnowledgeIngestResponse {
  ingested: number;
  skipped: number;
  errors: { filename: string; error: string }[];
  results: KnowledgeIngestFileResult[];
  indexing?: Record<string, unknown> | null;
}

export interface KnowledgeIndexResponse {
  bases: Record<string, unknown>;
  total_chunks: number;
  total_chunks_in_store: number;
  errors: { base?: string; error: string }[];
}

export interface WebIngestProgress {
  phase: string;
  current: number;
  total: number;
  percent: number;
  message: string;
  name?: string | null;
}

export interface KnowledgeWebIngestResponse {
  page_url: string;
  pages_fetched?: number;
  discovered: number;
  downloaded: number;
  ingested: number;
  skipped: number;
  errors: { stage?: string; error?: string; url?: string; filename?: string; source?: string }[];
  files: Record<string, unknown>[];
  indexing?: Record<string, unknown>;
}

export interface NormBulkIngestResponse {
  total_files: number;
  ingested: number;
  skipped: number;
  errors: { filename?: string; source?: string; error?: string }[];
  classified_preview?: {
    filename: string;
    norm_kind?: string;
    norm_code?: string;
    discipline?: string;
    confidence?: number;
    source?: string;
  }[];
  classified_count?: number;
  indexing?: Record<string, unknown>;
  report_filename?: string;
  report_csv?: string;
  audit_rows?: {
    filename: string;
    norm_kind?: string;
    norm_code?: string;
    discipline?: string;
    confidence?: number;
    status?: string;
    status_label?: string;
    reason?: string;
  }[];
}

export interface KnowledgeCatalogEntry {
  id: string;
  name?: string;
  description?: string;
  filename: string;
  path: string;
  discipline: string[];
  content_type: string;
  content_hash?: string;
  catalog_ts?: string;
  price_item_count?: number;
  has_price_items?: boolean;
  has_budget_model?: boolean;
  service_count?: number;
  is_active_price_base?: boolean;
}

export interface KnowledgeCatalogResponse {
  total: number;
  log_entries?: number;
  items: KnowledgeCatalogEntry[];
}

export interface KnowledgeNormStats {
  total: number;
  current_count: number;
  historical_count: number;
  without_year_count: number;
  nbr_count: number;
  nr_count: number;
  unknown_kind_count: number;
  unique_codes: number;
  multi_edition_codes: number;
  unique_editions: number;
  distinct_years: number;
}

export interface KnowledgeNbrCoverageStats {
  base: string;
  catalog_files: number;
  files_on_disk: number;
  files_missing_disk: number;
  indexed_files: number;
  effective_indexed_files?: number;
  dedup_only_files?: number;
  not_indexed_files: number;
  catalog_codes: number;
  indexed_codes: number;
  not_indexed_codes: number;
  faiss_chunks: number;
  coverage_pct: number;
  file_coverage_pct: number;
  effective_file_coverage_pct?: number;
  code_coverage_pct: number;
  healthy: boolean;
  sample_not_indexed: string[];
  sample_not_indexed_codes?: string[];
  sample_extra_indexed: string[];
}

export interface KnowledgeStatsResponse {
  catalog_total: number;
  catalog_log_entries?: number;
  catalog_superseded?: number;
  by_content_type: Record<string, number>;
  index: {
    multi_index?: Record<string, number>;
    total_multi_chunks?: number;
    index_names?: Record<string, string>;
  };
  norms?: KnowledgeNormStats;
  nbr_coverage?: KnowledgeNbrCoverageStats;
}

export interface MaintenanceConfigResponse {
  backup_drive_win: string;
  backup_staging_dir: string;
  keep_latest_sets: number;
  include_knowledge_pdfs: boolean;
  include_faiss: boolean;
  include_database: boolean;
  backup_staging_exists?: boolean;
  backup_drive_exists?: boolean;
  subfolders?: Record<string, boolean>;
  config_path?: string;
}

export interface MaintenanceStatusResponse {
  environment: {
    is_wsl: boolean;
    repo_root: string;
    platform: string;
  };
  config: Record<string, unknown>;
  history: MaintenanceBackupManifest[];
}

export interface MaintenanceBackupManifest {
  id: string;
  status: string;
  started_at: string;
  finished_at?: string;
  targets: string[];
  artifacts: Array<{
    target: string;
    path: string;
    size_bytes: number;
    size_human: string;
    warning?: string;
    started?: boolean;
  }>;
  errors: Array<{ target: string; error: string }>;
  manifest_file?: string;
}

export interface MaintenanceInitResponse {
  backup_staging_dir: string;
  backup_drive_win: string;
  created: string[];
  subfolders: Record<string, boolean>;
}

export interface MaintenanceRestoreInspectResponse {
  stamp: string;
  artifacts: Record<string, { path: string; size_bytes: number; source: string }>;
  missing: string[];
  manifest_local: string | null;
  manifest_drive: string | null;
  restorable: boolean;
}

export interface MaintenanceRestoreResponse {
  stamp: string;
  targets: string[];
  dry_run: boolean;
  started_at: string;
  finished_at?: string;
  status: string;
  steps: Array<Record<string, unknown>>;
  errors: Array<{ target: string; error: string }>;
}

export type DevServiceStatus = "running" | "stopped" | "unknown";

export interface DevServiceItem {
  id: string;
  label: string;
  description: string;
  group: string;
  port: number | null;
  managed: boolean;
  status: DevServiceStatus;
  detail: string;
  pid: number | null;
  log_file: string | null;
  can_start: boolean;
  can_stop: boolean;
}

export interface DevServicesResponse {
  services: DevServiceItem[];
  repo_root: string;
  hints: Record<string, string>;
}

export interface DevServiceActionResponse {
  id: string;
  status: string;
  message: string;
  pid?: number | null;
  log_file?: string | null;
  services: DevServiceItem[];
}

export interface DevStackStartResponse {
  results: Array<Record<string, unknown>>;
  services: DevServiceItem[];
}

export interface ShellRunResponse {
  ts: string;
  command: string;
  cwd: string;
  exit_code: number;
  output: string;
  success: boolean;
  truncated: boolean;
}

export interface ShellHistoryItem {
  ts: string;
  command: string;
  cwd: string;
  exit_code: number;
  truncated?: boolean;
}

export interface NormPackListItem {
  id: string;
  label: string;
  description: string;
  tags: string[];
  item_count: number;
  critical_count: number;
  agent_slug?: string | null;
  discipline?: string | null;
  group?: "transversal" | "disciplina" | string | null;
}

export interface NormPackListResponse {
  legal_notice: string;
  packs: NormPackListItem[];
}

export interface NormPackItemStatus {
  nbr_code: string;
  title: string;
  discipline: string;
  critical: boolean;
  status: "indexed" | "not_indexed" | "missing" | string;
  chunk_count: number;
  document_id?: string | null;
  filename?: string | null;
  file_path?: string | null;
  legal_source: string;
  upload_instruction?: string | null;
}

export interface NormPackSummary {
  total: number;
  indexed: number;
  not_indexed: number;
  missing: number;
  critical_missing: number;
  coverage_pct: number;
}

export interface NormPackAnalyzeResponse {
  pack_id: string;
  label: string;
  description: string;
  tags: string[];
  legal_notice: string;
  summary: NormPackSummary;
  items: NormPackItemStatus[];
}

export interface NormPackIndexResponse {
  pack_id: string;
  force: boolean;
  indexed_chunks: number;
  results: { nbr_code: string; status: string; chunks: number; error?: string }[];
  errors: { nbr_code?: string; error?: string }[];
  analysis_summary: NormPackSummary;
}

export interface NormPackChunkPreview {
  chunk_index: number;
  page?: number | null;
  filename?: string | null;
  edition_year?: number | null;
  text: string;
  char_count: number;
}

export interface NormPackNbrPreviewItem {
  nbr_code: string;
  title: string;
  filename?: string | null;
  edition_year?: number | null;
  legal_source: string;
  chunk_count: number;
  chunks: NormPackChunkPreview[];
}

export interface NormPackPreviewResponse {
  pack_id: string;
  pack_label: string;
  nbr_code_filter?: string | null;
  indexed_count: number;
  items: NormPackNbrPreviewItem[];
  preview_notice: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: {
    discipline?: string;
    agent?: string;
    extra?: Record<string, unknown>;
    raw?: ChatResponse;
    streaming?: boolean;
    streamStatus?: string;
    llmModel?: string;
  };
}

export interface BudgetRow {
  row_id: string;
  row_index?: number;
  code: string;
  name: string;
  level: number;
  quantity: number;
  unit: string;
  unit_cost: number;
  unit_cost_semd?: number;
  unit_price: number;
  unit_price_semd?: number;
  total_price: number;
  total_price_semd?: number;
  source_base: string;
  source_code: string;
  parent_code?: string;
  item_type: string;
  row_type?: string;
  bdi_rate?: number;
  bdi_label?: string;
  calculation_note?: string;
  editable: boolean;
  is_memory_row?: boolean;
  total_effective?: number;
  desoneracao_mode?: "comd" | "semd" | string;
  pricing_query?: string;
}

export interface BudgetProjectInfo {
  projeto?: string;
  objeto?: string;
  local?: string;
  endereco?: string;
  orcamento?: string;
  base_preco?: string;
  orgao?: string;
  empresa?: string;
  responsavel_tecnico?: string;
  obra_type?: string;
  price_bases?: BudgetPriceBaseSelection[];
  bdi?: {
    obra_type?: string;
    obra_label?: string;
    rate_com_desoneracao: number;
    rate_sem_desoneracao: number;
    label?: string;
  };
  template?: string;
}

export interface ScheduleLink {
  link_id: string;
  predecessor_id: string;
  successor_id: string;
  link_type: "FS" | "SS" | "FF" | "SF" | string;
  lag_days: number;
}

export interface ScheduleTask {
  task_id: string;
  budget_row_id: string;
  budget_code: string;
  name: string;
  row_type?: string;
  parent_code?: string | null;
  duration_days: number;
  is_summary?: boolean;
  manual_start?: string | null;
  early_start?: string | null;
  early_finish?: string | null;
  late_start?: string | null;
  late_finish?: string | null;
  total_float_days?: number | null;
  is_critical?: boolean;
}

export interface ProjectSchedule {
  project_start: string;
  project_end?: string | null;
  tasks: ScheduleTask[];
  links: ScheduleLink[];
  calculated_at?: string | null;
}

export interface BdiObraType {
  code: string;
  label: string;
  rate_com_desoneracao: number;
  rate_sem_desoneracao: number;
}

export interface PriceBaseInfo {
  id: string;
  name: string;
  filename: string;
  format: string;
  item_count: number;
  created_at: string;
  active: boolean;
}

export interface PriceBaseActiveStatus {
  loaded: boolean;
  source: "configured" | "memory" | "none" | string;
  base_id: string | null;
  base_name: string | null;
  item_count: number;
  hint?: string | null;
}

export interface PriceBankCounts {
  compositions_closed: number;
  compositions_open: number;
  insumos: number;
  open_items_total: number;
}

export interface PriceBankManifest {
  source: string;
  reference: string;
  uf?: string;
  desonerado?: boolean;
  synced_at?: string;
  counts: PriceBankCounts;
  metadata?: Record<string, unknown>;
}

export interface PriceBankReference {
  reference: string;
  label: string;
  source?: string;
  synced_at?: string;
  default_uf?: string;
  active?: boolean;
  counts?: PriceBankCounts;
  metadata?: Record<string, unknown>;
}

/** Base de preço selecionada na sessão de orçamento (UF + período por fonte). */
export interface BudgetPriceBaseSelection {
  source: string;
  label: string;
  enabled: boolean;
  uf: string;
  reference: string;
}

export interface PriceBankStats {
  loaded: boolean;
  manifest?: PriceBankManifest;
  counts: PriceBankCounts;
  sample_closed?: { code: string; description: string; unit: string; price: number }[];
  sample_open_codes?: string[];
  references?: PriceBankReference[];
  active_reference?: string;
}

export interface PriceBankInventoryPeriod {
  reference: string;
  label: string;
  synced_at?: string;
  default_uf?: string;
  active?: boolean;
  counts?: PriceBankCounts;
  metadata?: Record<string, unknown>;
}

export interface PriceBankInventoryGroup {
  source: string;
  label: string;
  auto_download?: boolean;
  periods: PriceBankInventoryPeriod[];
  last_sync?: PriceSyncSourceInfo["last_sync"];
}

export interface PriceBankInventory {
  totals: PriceBankCounts;
  period_count: number;
  source_count: number;
  groups: PriceBankInventoryGroup[];
  sources: PriceSyncSourceInfo[];
  active_reference?: string;
}

export interface PriceSyncSourceInfo {
  name: string;
  label: string;
  auto_download: boolean;
  download_url?: string;
  custom?: boolean;
  can_delete?: boolean;
  last_sync?: {
    source: string;
    status: string;
    reference?: string;
    item_count?: number;
    error?: string;
    synced_at?: string;
    metadata?: Record<string, unknown>;
  } | null;
}

export interface PriceSyncStatusResponse {
  sources: Record<string, unknown>;
  available: string[];
  bank: PriceBankStats;
}

export interface PriceSyncResult {
  source: string;
  status: string;
  reference?: string;
  item_count?: number;
  document_id?: string;
  path?: string;
  download?: { local_path: string; metadata?: Record<string, unknown> };
  ingest?: Record<string, unknown>;
  faiss?: Record<string, unknown>;
  providers?: Record<string, unknown>;
}

export interface OpenCompositionItem {
  item_type: string;
  code: string;
  description: string;
  unit: string;
  coefficient: number;
  unit_price: number;
  partial_cost: number;
  unit_price_sem?: number;
  partial_cost_sem?: number;
  /** Marcação AS = insumo/composição com preço de São Paulo (SEMINF tp2 ou SINAPI %AS). */
  tp2?: string;
  /** SINAPI ISD: SERVIÇOS, MATERIAL, MAO DE OBRA… */
  classificacao?: string;
  /** SINAPI ISD: C, CR… */
  origem_preco?: string;
  /** SINAPI Analítico: COM CUSTO, EM ESTUDO… */
  situacao?: string;
}

export interface CompositionPeriodVariationWarning {
  kind: "composition_total" | "item_unit_price";
  metric: "comd" | "semd";
  metric_label?: string;
  code?: string;
  description?: string;
  item_type?: string;
  current: number;
  previous: number;
  change_pct: number;
  message: string;
}

export interface CompositionPeriodVariation {
  previous_reference: string | null;
  previous_label: string | null;
  threshold_pct: number;
  warnings: CompositionPeriodVariationWarning[];
}

export interface OpenCompositionSummary {
  code: string;
  description: string;
  unit: string;
  total_price: number;
  total_price_sem: number;
  items_count: number;
  tp2?: string;
  match_kind?: "code" | "description";
}

export interface OpenCompositionListResponse {
  reference: string;
  uf: string;
  total: number;
  offset: number;
  limit: number;
  items: OpenCompositionSummary[];
}

export interface OpenCompositionSearchResponse {
  reference: string;
  uf: string;
  query: string;
  items: OpenCompositionSummary[];
}

export interface OpenCompositionDetail {
  code: string;
  description: string;
  unit: string;
  total_price: number;
  total_price_sem?: number;
  price_uf?: string;
  available_ufs?: string[];
  analytical_total_com?: number;
  analytical_total_sem?: number;
  /** SINAPI: grupo da composição (ex. Alvenaria de Vedação). */
  grupo?: string;
  /** SINAPI %AS com desoneração (fração 0–1). */
  pct_as_comd?: number;
  /** SINAPI %AS sem desoneração (fração 0–1). */
  pct_as_semd?: number;
  /** tp2 unificado: AS = São Paulo (%AS SINAPI ou coluna tp2 SEMINF). */
  tp2?: string;
  /** Encargos sociais Horista/Mensalista para a UF consultada. */
  labor_charges?: {
    localidade?: string;
    horista_comd?: number;
    mensalista_comd?: number;
    horista_semd?: number;
    mensalista_semd?: number;
  };
  period_variation?: CompositionPeriodVariation;
  items: OpenCompositionItem[];
}

export interface BudgetGenerateRequest {
  text: string;
  source_priority?: string[];
  use_llm?: boolean;
  obra_type?: string;
  existing_session_id?: string;
}

export type BudgetStreamEventType =
  | "status"
  | "token"
  | "step"
  | "done"
  | "error"
  | "pricing_resolve";

export interface BudgetStreamEvent {
  type: BudgetStreamEventType | string;
  data: Record<string, unknown>;
}

export interface TechSpecFormatting {
  font_family: string;
  font_size: number;
  line_spacing: number;
  margin_cm: number;
  margin_top_cm?: number;
  margin_bottom_cm?: number;
  margin_left_cm?: number;
  margin_right_cm?: number;
  page_numbers?: boolean;
  page_number_position?: "left" | "center" | "right";
  text_align?: "justify" | "left" | "center";
  header_text?: string | null;
  logo_text?: string | null;
  document_title?: string | null;
}

export interface TechSpecDocument {
  title: string;
  markdown: string;
  html_content: string;
  formatting: TechSpecFormatting;
  llm_model?: string | null;
  updated_at?: string;
}

export interface TechSpecStreamEvent {
  type: "status" | "log" | "token" | "preview" | "done" | "error" | string;
  data: Record<string, unknown>;
}

export interface BudgetSkeletonSubEtapa {
  name: string;
}

export interface BudgetSkeletonEtapa {
  name: string;
  sub_etapas: BudgetSkeletonSubEtapa[];
}

export interface BudgetSkeleton {
  id: string;
  name: string;
  description: string;
  obra_type: string;
  etapas: BudgetSkeletonEtapa[];
  created_at?: string;
  updated_at?: string;
}

export interface BudgetSummary {
  id: string;
  title: string;
  orcamento?: string;
  project_id?: string | null;
  session_id: string;
  grand_total: number;
  obra_type: string;
  input_text?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BudgetSessionResponse {
  session_id: string;
  title: string;
  rows: BudgetRow[];
  items: Record<string, unknown>[];
  grand_total: number;
  grand_total_comd?: number;
  grand_total_semd?: number;
  desoneracao_mode?: "comd" | "semd" | string;
  currency: string;
  project?: BudgetProjectInfo;
  template?: string;
  calculation_memory: Record<string, unknown>[];
  schedule?: ProjectSchedule | null;
  tech_spec?: TechSpecDocument | null;
  source_priority: string[];
  intent: Record<string, unknown>;
  project_import?: {
    filename: string;
    format: string;
    segments: number;
    chars_extracted: number;
  };
  pipeline?: {
    steps: string[];
    intent: Record<string, unknown>;
    quantity_memory: Record<string, unknown>[];
    parser: string;
    llm_model?: string | null;
    llm_used?: boolean;
  };
  input_text?: string;
  db_id?: string;
  project_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PricingProviderInfo {
  name: string;
  label: string;
  loaded: boolean;
  item_count: number;
  source?: Record<string, unknown> | null;
}

export interface PricingProvidersResponse {
  data_dir: string;
  providers: PricingProviderInfo[];
}

export interface ReviewScores {
  conformidade_geral?: number;
  conformidade_estrutural?: number;
  conformidade_pci?: number;
  conformidade_documental?: number;
  conformidade_orcamentaria?: number;
}

export interface ReviewSummary {
  id: string;
  project_id: string;
  version: number;
  status: string;
  scores?: ReviewScores | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  ncs_created?: number;
  files_processed?: number;
}

export interface ReviewDetail extends ReviewSummary {
  analysis_payload?: Record<string, unknown> | null;
  report_payload?: Record<string, unknown> | null;
  parent_review_id?: string | null;
}

export interface ReviewListResponse {
  total: number;
  items: ReviewSummary[];
}

export interface NCSummary {
  id: string;
  project_id: string;
  review_id?: string | null;
  codigo: string;
  categoria: string;
  criticidade: string;
  descricao: string;
  evidencia?: string | null;
  norma?: string | null;
  impacto?: string | null;
  recomendacao?: string | null;
  status: string;
}

export interface NCListResponse {
  total: number;
  items: NCSummary[];
}

export interface ReviewDashboard {
  project_id?: string | null;
  reviews_total: number;
  ncs_total: number;
  latest_review?: ReviewSummary | null;
  scores?: ReviewScores | null;
  pending_ncs: number;
}

export interface DigitalTwin {
  id: string;
  project_id: string;
  disciplinas?: string[] | null;
  elementos?: Record<string, unknown> | null;
  documentos?: unknown[] | null;
  normas_aplicaveis?: string[] | null;
  payload?: Record<string, unknown> | null;
  versao: number;
  created_at?: string | null;
}

export interface VisionModeItem {
  value: string;
  label: string;
}

export interface VisionStatusResponse {
  available: boolean;
  ollama_reachable: boolean;
  vision_models_ready: string[];
  primary: string;
  technical_model?: string;
  error?: string | null;
}

export interface VisionAnalysisItem {
  project_file_id: string;
  filename: string;
  analysis_mode: string;
  analyzer?: string | null;
  skipped: boolean;
  error?: string | null;
  model_used?: string | null;
  technical_model_used?: string | null;
  analyzed_at?: string | null;
  analysis?: Record<string, unknown> | null;
  technical_report?: Record<string, unknown> | null;
  rag_sources?: Array<Record<string, unknown>>;
  normative_context?: Record<string, unknown> | null;
}

export interface PciChecklistItem {
  id: string;
  norma: string;
  titulo: string;
  descricao: string;
  status: "conforme" | "parcial" | "pendente" | "nao_aplicavel";
  evidencias: string[];
  observacao?: string;
}

export interface PciChecklistResponse {
  project_id: string;
  modo: string;
  total_itens: number;
  conformes: number;
  parciais: number;
  pendentes: number;
  nao_aplicaveis: number;
  score_percent: number;
  pronto_cbmam: boolean;
  arquivos_analisados: number;
  rag_audit: Record<string, unknown>;
  itens: PciChecklistItem[];
}

export interface VisionAnalyzeResponse {
  project_id: string;
  mode: string;
  total: number;
  analyzed: number;
  errors: number;
  skipped: number;
  items: VisionAnalysisItem[];
  summary: Record<string, unknown>;
  pci_checklist?: PciChecklistResponse | null;
}

export interface VisionAnalyzeProgress {
  phase: string;
  current: number;
  total: number;
  percent: number;
  message: string;
  filename?: string | null;
  file_id?: string | null;
}

export interface VisionAnalysisListResponse {
  total: number;
  items: VisionAnalysisItem[];
}

export interface VisionReportRequest {
  report_type:
    | "relatorio_fotografico"
    | "laudo"
    | "correcoes"
    | "tecnico"
    | "review"
    | "nc"
    | "parecer"
    | "memorial"
    | "tdr";
  file_ids?: string[];
  obra_info?: string;
  solicitante?: string;
  objeto?: string;
  discipline?: string;
  prazo?: string;
}

export interface WorkspaceToolItem {
  id: string;
  label: string;
  available: boolean;
  supports: string[];
}

export interface VisionWorkspaceStatusResponse {
  ready: boolean;
  ollama_reachable: boolean;
  vision_model: string;
  vision_model_ready: boolean;
  technical_model: string;
  technical_model_ready: boolean;
  installed_models: string[];
  analyzers: WorkspaceToolItem[];
  reports: { id: string; label: string; route: string }[];
  dependencies: Record<string, boolean>;
  pipeline: string[];
  frontend_routes: string[];
}

export interface ActivityEventItem {
  id: string;
  project_id?: string | null;
  source: string;
  event_type: string;
  title: string;
  summary?: string | null;
  agent_name?: string | null;
  discipline?: string | null;
  phase?: string | null;
  meta?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface ActivityListResponse {
  total: number;
  items: ActivityEventItem[];
}

export interface DecisionItem {
  id: string;
  project_id?: string | null;
  source: string;
  title: string;
  description?: string | null;
  rationale?: string | null;
  disciplines?: string[] | null;
  meta?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface DecisionListResponse {
  total: number;
  items: DecisionItem[];
}

export interface ConsoleAgentRunItem {
  id: string;
  agent_name?: string | null;
  discipline?: string | null;
  result_text?: string | null;
  had_context?: boolean;
  created_at?: string | null;
}

export interface ConsoleLogItem {
  id: string;
  conversation_id?: string | null;
  project_id?: string | null;
  input_text: string;
  disciplines: string[];
  final_report?: string | null;
  synthesis?: Record<string, unknown> | null;
  use_rag?: boolean;
  agent_count?: number;
  created_at?: string | null;
  agent_runs: ConsoleAgentRunItem[];
}

export interface ConsoleLogsResponse {
  total: number;
  items: ConsoleLogItem[];
}

export interface ConsoleStatsResponse {
  orchestrator_logs: number;
  agent_runs: number;
  activity_events: number;
  decisions: number;
}

export interface OllamaRunningModel {
  name: string;
  size_vram_mb: number;
  context_length?: number | null;
  expires_at?: string | null;
}

export interface RuntimeJobItem {
  id: string;
  kind: string;
  label: string;
  project_id?: string | null;
  model?: string | null;
  phase?: string | null;
  message?: string | null;
  percent?: number | null;
  current?: number | null;
  total?: number | null;
  status: string;
  cancel_requested?: boolean;
  elapsed_sec?: number | null;
  meta?: Record<string, unknown> | null;
}

export interface OllamaQueueItem {
  job_id: string;
  kind: string;
  label: string;
  model?: string | null;
  state: "on_gpu" | "running" | "queued" | string;
  position: number;
  message?: string | null;
  phase?: string | null;
}

export interface OllamaQueueSnapshot {
  depth: number;
  waiting_count: number;
  on_gpu_count: number;
  loaded_slots: number;
  items: OllamaQueueItem[];
}

export interface OpsLogItem {
  id: string;
  ts: number;
  source: string;
  level: string;
  message: string;
  project_id?: string | null;
  job_id?: string | null;
  phase?: string | null;
  meta?: Record<string, unknown> | null;
  elapsed_sec?: number | null;
}

export interface VramModelSegment {
  name: string;
  size_vram_mb: number;
  percent_of_total: number;
}

export interface VramSnapshot {
  available: boolean;
  total_mb?: number | null;
  used_mb?: number | null;
  free_mb?: number | null;
  utilization_percent?: number | null;
  memory_percent?: number | null;
  ollama_allocated_mb: number;
  other_mb?: number | null;
  models: VramModelSegment[];
}

export interface ConsoleLiveResponse {
  timestamp?: number | null;
  ollama_reachable: boolean;
  ollama_error?: string | null;
  loaded_models: OllamaRunningModel[];
  gpu?: Record<string, unknown> | null;
  cpu_percent?: number | null;
  memory_percent?: number | null;
  active_jobs: RuntimeJobItem[];
  recent_jobs: RuntimeJobItem[];
  active_job_count: number;
  loaded_model_count: number;
  ollama_queue?: OllamaQueueSnapshot | null;
  ops_logs?: OpsLogItem[];
  vram?: VramSnapshot | null;
}

export interface UnloadResponse {
  ok: boolean;
  unloaded?: string[];
  errors?: { model: string; error: string }[];
  error?: string | null;
}
