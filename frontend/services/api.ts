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
  ModelsStatusResponse,
  BdiObraType,
  BudgetGenerateRequest,
  BudgetSessionResponse,
  BudgetStreamEvent,
  BudgetSummary,
  PricingProvidersResponse,
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
    throw new Error(formatApiError(errorText, response.status));
  }

  return response.json() as Promise<T>;
}

export function formatApiError(errorText: string, status?: number): string {
  const trimmed = errorText.trim();
  if (!trimmed) return status ? `Erro HTTP ${status}` : "Erro desconhecido";
  try {
    const parsed = JSON.parse(trimmed) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (parsed.detail != null) return JSON.stringify(parsed.detail);
  } catch {
    /* texto puro */
  }
  return trimmed;
}

export function isSessionNotFoundError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return msg.includes("Sessão não encontrada") || msg.includes("Sessao nao encontrada");
}

const BUDGET_SESSION_RESTORED = "budget-session-restored";

let budgetSessionSnapshot: BudgetSessionResponse | null = null;

export function syncBudgetSessionSnapshot(session: BudgetSessionResponse | null): void {
  budgetSessionSnapshot = session;
}

async function restoreBudgetSessionSnapshot(): Promise<BudgetSessionResponse> {
  if (!budgetSessionSnapshot?.session_id) {
    throw new Error("Sessão não encontrada");
  }
  const restored = await request<BudgetSessionResponse>("/pricing/budget/restore", {
    method: "POST",
    body: JSON.stringify({ payload: budgetSessionSnapshot }),
  });
  budgetSessionSnapshot = restored;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(BUDGET_SESSION_RESTORED, { detail: restored }));
  }
  return restored;
}

async function withBudgetSessionRecovery<T>(
  sessionId: string,
  fn: (sid: string) => Promise<T>
): Promise<T> {
  try {
    return await fn(sessionId);
  } catch (err) {
    if (!isSessionNotFoundError(err) || !budgetSessionSnapshot) throw err;
    const restored = await restoreBudgetSessionSnapshot();
    return fn(restored.session_id);
  }
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

export async function* budgetGenerateStream(
  body: BudgetGenerateRequest,
  signal?: AbortSignal
): AsyncGenerator<BudgetStreamEvent> {
  const response = await fetch(`${API_BASE_URL}/pricing/budget/generate/stream`, {
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
  if (!reader) throw new Error("Streaming não suportado");

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
      if (event) yield event as BudgetStreamEvent;
    }
  }
  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim());
    if (event) yield event as BudgetStreamEvent;
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

  budgetGenerateStream,

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

  modelsStatus(): Promise<ModelsStatusResponse> {
    return request<ModelsStatusResponse>("/models/status");
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

  knowledgeActivatePriceBase(documentId: string): Promise<{ activated: string; item_count: number; name?: string }> {
    return request(`/knowledge/documents/${documentId}/activate-price-base`, { method: "POST" });
  },

  knowledgeIndexBudgetModel(documentId: string): Promise<{
    document_id: string;
    status: string;
    service_count: number;
    budget_model_indexed: number;
    reason?: string;
  }> {
    return request(`/knowledge/documents/${documentId}/index-budget-model`, { method: "POST" });
  },

  knowledgeUpdateDocument(
    documentId: string,
    payload: {
      name?: string;
      description?: string;
      content_type?: string;
      discipline?: string;
    }
  ): Promise<{
    updated: string;
    name: string;
    description: string;
    content_type: string;
    discipline: string[];
    filename: string;
  }> {
    return request(`/knowledge/documents/${documentId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  knowledgeDeleteDocument(documentId: string): Promise<{
    deleted: string;
    filename: string;
    was_active_price_base: boolean;
    catalog_entries_removed: number;
    faiss_chunks_removed: number;
    files_removed: string[];
  }> {
    return request(`/knowledge/documents/${documentId}`, { method: "DELETE" });
  },

  pricingProviders(): Promise<PricingProvidersResponse> {
    return request<PricingProvidersResponse>("/pricing/providers");
  },

  pricingBdiTypes(): Promise<{ types: BdiObraType[]; default: string }> {
    return request("/pricing/bdi/types");
  },

  pricingOllamaStatus(): Promise<{
    available: boolean;
    url: string;
    budget_model: string;
    models: string[];
    hint?: string | null;
  }> {
    return request("/pricing/ollama/status");
  },

  pricingUpdateBdi(sessionId: string, obraType: string): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request<BudgetSessionResponse>(`/pricing/budget/${sid}/bdi`, {
        method: "PATCH",
        body: JSON.stringify({ obra_type: obraType }),
      })
    );
  },

  pricingGenerate(body: BudgetGenerateRequest): Promise<BudgetSessionResponse> {
    return request<BudgetSessionResponse>("/pricing/budget/generate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  pricingSession(sessionId: string): Promise<BudgetSessionResponse> {
    return request<BudgetSessionResponse>(`/pricing/budget/${sessionId}`);
  },

  pricingUpdateCell(
    sessionId: string,
    body: { row_id: string; field: string; value: string | number; code?: string }
  ): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request<BudgetSessionResponse>(`/pricing/budget/${sid}/cell`, {
        method: "PATCH",
        body: JSON.stringify(body),
      })
    );
  },

  pricingExportUrl(sessionId: string): string {
    return `${API_BASE_URL}/pricing/budget/${sessionId}/export`;
  },

  async pricingUploadBase(provider: string, file: File): Promise<Record<string, unknown>> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE_URL}/pricing/providers/${provider}/upload`, {
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

  pricingReloadBases(): Promise<{ reloaded: Record<string, number> }> {
    return request("/pricing/bases/reload", { method: "POST" });
  },

  pricingImportPpd(file?: File): Promise<BudgetSessionResponse> {
    if (file) {
      const formData = new FormData();
      formData.append("file", file);
      return fetch(`${API_BASE_URL}/pricing/budget/import-ppd`, {
        method: "POST",
        headers: getMultipartAuthHeaders(),
        body: formData,
      }).then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
        return r.json();
      });
    }
    return request<BudgetSessionResponse>("/pricing/budget/import-ppd", { method: "POST" });
  },

  pricingLoadPpdExample(): Promise<{ loaded: number; source: string }> {
    return request("/pricing/budget/load-ppd-example", { method: "POST" });
  },

  pricingListBases(): Promise<{ bases: PriceBaseInfo[]; active?: PriceBaseActiveStatus }> {
    return request("/pricing/bases");
  },

  async pricingImportBase(name: string, file: File): Promise<{ base: PriceBaseInfo; loaded: number }> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(
      `${API_BASE_URL}/pricing/bases/import?name=${encodeURIComponent(name)}`,
      { method: "POST", headers: getMultipartAuthHeaders(), body: formData }
    );
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  pricingActivateBase(baseId: string): Promise<{ activated: string; item_count: number; base: PriceBaseInfo }> {
    return request(`/pricing/bases/${baseId}/activate`, { method: "POST" });
  },

  pricingDeleteBase(baseId: string): Promise<{ deleted: string; removed: PriceBaseInfo }> {
    return request(`/pricing/bases/${baseId}`, { method: "DELETE" });
  },

  pricingImportExampleBase(): Promise<{ base: PriceBaseInfo; loaded: number; reactivated: boolean }> {
    return request("/pricing/bases/import-example", { method: "POST" });
  },

  pricingNewTemplate(obraType: string, projeto = ""): Promise<BudgetSessionResponse> {
    const params = new URLSearchParams({ obra_type: obraType });
    if (projeto) params.set("projeto", projeto);
    return request(`/pricing/budget/new-template?${params}`, { method: "POST" });
  },

  async pricingImportProject(
    file: File,
    useLlm = true,
    obraType?: string
  ): Promise<BudgetSessionResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams({ use_llm: String(useLlm) });
    if (obraType) params.set("obra_type", obraType);
    const response = await fetch(
      `${API_BASE_URL}/pricing/budget/import-project?${params}`,
      { method: "POST", headers: getMultipartAuthHeaders(), body: formData }
    );
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  pricingListSaved(): Promise<{ items: BudgetSummary[] }> {
    return request("/pricing/budget/saved");
  },

  pricingGetSaved(id: string): Promise<BudgetSessionResponse> {
    return request(`/pricing/budget/saved/${id}`);
  },

  pricingSaveBudget(body: {
    title?: string;
    input_text?: string;
    payload: BudgetSessionResponse;
  }): Promise<BudgetSessionResponse> {
    return request("/pricing/budget/saved", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  pricingUpdateSaved(
    id: string,
    body: { title?: string; input_text?: string; payload: BudgetSessionResponse }
  ): Promise<BudgetSessionResponse> {
    return request(`/pricing/budget/saved/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  pricingDeleteSaved(id: string): Promise<{ deleted: string }> {
    return request(`/pricing/budget/saved/${id}`, { method: "DELETE" });
  },

  pricingResolve(query: string, limit = 10): Promise<{ best: Record<string, unknown> | null; results: Record<string, unknown>[]; query: string }> {
    return request("/pricing/resolve", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    });
  },

  pricingSearchPrices(
    query: string,
    limit = 15
  ): Promise<{
    query: string;
    parsed_query?: string;
    unit_hint?: string;
    parsed_quantity?: number | null;
    parsed?: { query?: string; unit_hint?: string | null; quantity?: number | null };
    results: Record<string, unknown>[];
    count: number;
  }> {
    return request("/pricing/budget/search", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    });
  },

  pricingUpdateProject(sessionId: string, body: Record<string, string | undefined>): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/project`, {
        method: "PATCH",
        body: JSON.stringify(body),
      })
    );
  },

  pricingAddEtapa(sessionId: string, name: string): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/etapas`, {
        method: "POST",
        body: JSON.stringify({ name }),
      })
    );
  },

  pricingUpdateEtapa(sessionId: string, etapaCode: string, name: string): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/etapas/${encodeURIComponent(etapaCode)}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      })
    );
  },

  pricingDeleteRow(sessionId: string, rowId: string): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/rows/${encodeURIComponent(rowId)}`, {
        method: "DELETE",
      })
    );
  },

  pricingRenumberItemization(
    sessionId: string
  ): Promise<BudgetSessionResponse & { renumber_result?: { changed_count: number; mapping: Record<string, string> } }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/itemization/renumber`, {
        method: "POST",
      })
    );
  },

  pricingComposeEtapa(
    sessionId: string,
    etapaCode: string,
    prompt: string,
    defaultQuantity?: number,
    replaceExisting = false
  ): Promise<{ session: BudgetSessionResponse; compose_log: Record<string, unknown>[]; removed_count?: number }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/etapas/${encodeURIComponent(etapaCode)}/compose`, {
        method: "POST",
        body: JSON.stringify({
          prompt,
          replace_existing: replaceExisting,
          ...(defaultQuantity != null && defaultQuantity >= 0 ? { default_quantity: defaultQuantity } : {}),
        }),
      })
    );
  },

  pricingGetGroupComposePrompt(
    sessionId: string,
    groupCode: string
  ): Promise<{ prompt: string; service_count: number }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/groups/${encodeURIComponent(groupCode)}/compose-prompt`)
    );
  },

  pricingReplaceService(
    sessionId: string,
    rowId: string,
    body: {
      code?: string;
      description?: string;
      unit?: string;
      price?: number;
      source?: string;
      query?: string;
    }
  ): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/services/${encodeURIComponent(rowId)}/replace`, {
        method: "POST",
        body: JSON.stringify(body),
      })
    );
  },

  pricingApplyGroupQuantity(
    sessionId: string,
    groupCode: string,
    quantity: number,
    includeSubgroups = true
  ): Promise<{ session: BudgetSessionResponse; updated_count: number }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(
        `/pricing/budget/${sid}/groups/${encodeURIComponent(groupCode)}/apply-quantity`,
        {
          method: "POST",
          body: JSON.stringify({ quantity, include_subgroups: includeSubgroups }),
        }
      )
    );
  },

  pricingAddService(
    sessionId: string,
    body: {
      etapa_code: string;
      code?: string;
      description?: string;
      unit?: string;
      price?: number;
      source?: string;
      quantity?: number;
      query?: string;
    }
  ): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/services`, {
        method: "POST",
        body: JSON.stringify(body),
      })
    );
  },

  pricingAddSubetapa(sessionId: string, parentCode: string, name: string): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/subetapas`, {
        method: "POST",
        body: JSON.stringify({ parent_code: parentCode, name }),
      })
    );
  },

  pricingGenerateMemories(
    sessionId: string,
    groupCode?: string,
    useLlm = false,
    llmModel?: string
  ): Promise<{ session: BudgetSessionResponse; memory_log: Record<string, unknown>[] }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/memory/generate`, {
        method: "POST",
        body: JSON.stringify({
          group_code: groupCode || null,
          use_llm: useLlm,
          llm_model: llmModel && llmModel !== "auto" ? llmModel : null,
        }),
      })
    );
  },

  pricingSyncSchedule(sessionId: string): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/schedule/sync`, { method: "POST" })
    );
  },

  pricingRecalculateSchedule(sessionId: string): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/schedule/recalculate`, { method: "POST" })
    );
  },

  pricingUpdateScheduleSettings(
    sessionId: string,
    projectStart: string
  ): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/schedule/settings`, {
        method: "PATCH",
        body: JSON.stringify({ project_start: projectStart }),
      })
    );
  },

  pricingUpdateScheduleTask(
    sessionId: string,
    taskId: string,
    body: { duration_days?: number; manual_start?: string | null }
  ): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/schedule/tasks/${taskId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      })
    );
  },

  pricingAddScheduleLink(
    sessionId: string,
    body: {
      predecessor_id: string;
      successor_id: string;
      link_type?: string;
      lag_days?: number;
    }
  ): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/schedule/links`, {
        method: "POST",
        body: JSON.stringify(body),
      })
    );
  },

  pricingDeleteScheduleLink(sessionId: string, linkId: string): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/schedule/links/${linkId}`, { method: "DELETE" })
    );
  },

  pricingComposeSchedule(
    sessionId: string,
    prompt: string,
    options?: { useLlm?: boolean; replaceLinks?: boolean; llmModel?: string }
  ): Promise<{
    session: BudgetSessionResponse;
    schedule_log: { action: string; status: string; detail?: string }[];
    summary: string;
    llm_model?: string | null;
  }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/schedule/compose`, {
        method: "POST",
        body: JSON.stringify({
          prompt,
          use_llm: options?.useLlm ?? true,
          replace_links: options?.replaceLinks ?? false,
          llm_model: options?.llmModel && options.llmModel !== "auto" ? options.llmModel : null,
        }),
      })
    );
  },

  async pricingImportModelTemplate(file: File, sessionId?: string): Promise<BudgetSessionResponse & { imported_etapas?: number }> {
    const form = new FormData();
    form.append("file", file);
    const params = new URLSearchParams();
    if (sessionId) params.set("session_id", sessionId);
    const qs = params.toString();
    const response = await fetch(
      `${API_BASE_URL}/pricing/budget/import-model-template${qs ? `?${qs}` : ""}`,
      { method: "POST", headers: getMultipartAuthHeaders(), body: form }
    );
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Erro HTTP ${response.status}`);
    }
    return response.json();
  },
};

export { API_BASE_URL, BUDGET_SESSION_RESTORED };
