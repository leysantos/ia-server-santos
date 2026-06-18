export interface ChatRequest {
  text: string;
  use_rag?: boolean;
  persist?: boolean;
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
  };
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
  input_text: string;
  mode: "single" | "multi";
  created_at?: string;
  updated_at?: string;
  orchestrator_logs?: OrchestratorLogItem[];
  agent_runs?: AgentRunItem[];
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
  };
}
