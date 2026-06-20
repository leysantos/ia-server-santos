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
}

export interface SystemBenchmarkResponse {
  available: boolean;
  error?: string;
  timestamp?: number;
  cpu?: SystemBenchmarkMetric;
  memory?: SystemBenchmarkMetric;
  gpu?: SystemBenchmarkMetric;
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
  reason?: string;
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
  errors: { stage?: string; error?: string; url?: string }[];
  files: Record<string, unknown>[];
  indexing?: Record<string, unknown>;
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

export interface KnowledgeStatsResponse {
  catalog_total: number;
  catalog_log_entries?: number;
  by_content_type: Record<string, number>;
  index: {
    multi_index?: Record<string, number>;
    total_multi_chunks?: number;
    index_names?: Record<string, string>;
  };
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
  page_numbers?: boolean;
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

export interface BudgetSummary {
  id: string;
  title: string;
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
