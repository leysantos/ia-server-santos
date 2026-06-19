import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  ConversationDetail,
  ConversationListResponse,
  HealthResponse,
  HistoryResponse,
  KnowledgeCatalogResponse,
  KnowledgeIndexResponse,
  KnowledgeIngestResponse,
  KnowledgeOptionsResponse,
  KnowledgeStatsResponse,
  OrchestrateRequest,
  OrchestrateResponse,
  SystemBenchmarkResponse,
  ProjectDetail,
  ProjectFormatsResponse,
  ProjectListResponse,
  ProjectSummary,
  ConversationSummary,
  WorkspaceSearchResponse,
} from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Headers para JSON — inclui Content-Type */
function getAuthHeaders(): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  if (typeof window !== "undefined") {
    const token = localStorage.getItem("ia_auth_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const tenantId = localStorage.getItem("ia_tenant_id");
    if (tenantId) {
      headers["X-Tenant-Id"] = tenantId;
    }
  }

  return headers;
}

/** Headers para multipart — sem Content-Type (boundary automático) */
function getMultipartAuthHeaders(): HeadersInit {
  const headers: HeadersInit = {};

  if (typeof window !== "undefined") {
    const token = localStorage.getItem("ia_auth_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const tenantId = localStorage.getItem("ia_tenant_id");
    if (tenantId) {
      headers["X-Tenant-Id"] = tenantId;
    }
  }

  return headers;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Erro HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function parseSseBlock(block: string): ChatStreamEvent | null {
  let eventType = "message";
  let dataLine = "";

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLine = line.slice(5).trim();
    }
  }

  if (!dataLine) return null;

  try {
    return { type: eventType, data: JSON.parse(dataLine) } as ChatStreamEvent;
  } catch {
    return null;
  }
}

export async function* chatStream(
  body: ChatRequest,
  signal?: AbortSignal
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Erro HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Streaming não suportado neste navegador");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";

    for (const block of blocks) {
      const event = parseSseBlock(block.trim());
      if (event) yield event;
    }
  }

  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim());
    if (event) yield event;
  }
}

export const api = {
  chat(body: ChatRequest): Promise<ChatResponse> {
    return request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  chatStream,

  orchestrate(body: OrchestrateRequest): Promise<OrchestrateResponse> {
    return request<OrchestrateResponse>("/orchestrate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  history(limit = 50, conversationId?: string): Promise<HistoryResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (conversationId) {
      params.set("conversation_id", conversationId);
    }
    return request<HistoryResponse>(`/history?${params.toString()}`);
  },

  conversations(limit = 50, projectId?: string, unassignedOnly = false): Promise<ConversationListResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (projectId) params.set("project_id", projectId);
    if (unassignedOnly) params.set("unassigned_only", "true");
    return request<ConversationListResponse>(`/conversations?${params.toString()}`);
  },

  conversation(id: string): Promise<ConversationDetail> {
    return request<ConversationDetail>(`/conversations/${id}`);
  },

  updateConversation(
    id: string,
    body: { title?: string; project_id?: string | null }
  ): Promise<ConversationSummary> {
    return request<ConversationSummary>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteConversation(id: string): Promise<{ deleted: boolean; id: string }> {
    return request(`/conversations/${id}`, { method: "DELETE" });
  },

  projects(limit = 50): Promise<ProjectListResponse> {
    return request<ProjectListResponse>(`/projects?limit=${limit}`);
  },

  projectFormats(): Promise<ProjectFormatsResponse> {
    return request<ProjectFormatsResponse>("/projects/formats");
  },

  createProject(name: string, description?: string): Promise<ProjectSummary> {
    return request<ProjectSummary>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  },

  project(id: string): Promise<ProjectDetail> {
    return request<ProjectDetail>(`/projects/${id}`);
  },

  updateProject(
    id: string,
    body: { name?: string; description?: string }
  ): Promise<ProjectSummary> {
    return request<ProjectSummary>(`/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteProject(id: string): Promise<{ deleted: boolean; id: string }> {
    return request(`/projects/${id}`, { method: "DELETE" });
  },

  async uploadProjectFiles(
    projectId: string,
    files: File[]
  ): Promise<{
    uploaded: number;
    files: unknown[];
    indexing?: { status?: string; chunks?: number; filename?: string }[];
  }> {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/files`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: formData,
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Erro HTTP ${response.status}`);
    }
    return response.json();
  },

  deleteProjectFile(projectId: string, fileId: string): Promise<{ deleted: boolean; id: string }> {
    return request(`/projects/${projectId}/files/${fileId}`, { method: "DELETE" });
  },

  reindexProject(projectId: string): Promise<Record<string, unknown>> {
    return request(`/projects/${projectId}/reindex`, { method: "POST" });
  },

  searchWorkspace(q: string, limit = 30): Promise<WorkspaceSearchResponse> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return request<WorkspaceSearchResponse>(`/workspace/search?${params.toString()}`);
  },

  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  systemBenchmark(): Promise<SystemBenchmarkResponse> {
    return request<SystemBenchmarkResponse>("/system/benchmark");
  },

  knowledgeOptions(): Promise<KnowledgeOptionsResponse> {
    return request<KnowledgeOptionsResponse>("/knowledge/options");
  },

  knowledgeStats(): Promise<KnowledgeStatsResponse> {
    return request<KnowledgeStatsResponse>("/knowledge/stats");
  },

  knowledgeCatalog(limit = 50): Promise<KnowledgeCatalogResponse> {
    return request<KnowledgeCatalogResponse>(`/knowledge/catalog?limit=${limit}`);
  },

  async knowledgeIngest(formData: FormData): Promise<KnowledgeIngestResponse> {
    const response = await fetch(`${API_BASE_URL}/knowledge/ingest`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: formData,
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Erro HTTP ${response.status}`);
    }
    return response.json() as Promise<KnowledgeIngestResponse>;
  },

  knowledgeIndex(base?: string, force = false): Promise<KnowledgeIndexResponse> {
    return request<KnowledgeIndexResponse>("/knowledge/index", {
      method: "POST",
      body: JSON.stringify({ base: base ?? null, force }),
    });
  },
};

export { API_BASE_URL };
