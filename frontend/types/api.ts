export interface ChatRequest {
  text: string;
  use_rag?: boolean;
  persist?: boolean;
  conversation_id?: string;
  project_id?: string;
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

export interface KnowledgeOptionsResponse {
  disciplines: KnowledgeOptionItem[];
  content_types: KnowledgeOptionItem[];
  bases: KnowledgeOptionItem[];
  extensions: string[];
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

export interface KnowledgeCatalogEntry {
  id: string;
  filename: string;
  path: string;
  discipline: string[];
  content_type: string;
  content_hash?: string;
  catalog_ts?: string;
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
