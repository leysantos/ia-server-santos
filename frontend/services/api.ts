import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  ConversationDetail,
  ConversationListResponse,
  HealthResponse,
  HistoryResponse,
  KnowledgeCatalogResponse,
  DocumentTypePreset,
  KnowledgeIndexResponse,
  KnowledgeIngestResponse,
  KnowledgeOptionsResponse,
  KnowledgeStatsResponse,
  KnowledgeWebIngestResponse,
  NormBulkIngestResponse,
  NormPackAnalyzeResponse,
  NormPackIndexResponse,
  NormPackListResponse,
  NormPackPreviewResponse,
  WebIngestProgress,
  ModelsStatusResponse,
  BdiObraType,
  BudgetGenerateRequest,
  BudgetPriceBaseSelection,
  BudgetSessionResponse,
  BudgetSkeleton,
  BudgetSkeletonEtapa,
  BudgetStreamEvent,
  BudgetSummary,
  TechSpecDocument,
  TechSpecFormatting,
  TechSpecStreamEvent,
  PricingProvidersResponse,
  OrchestrateRequest,
  OrchestrateResponse,
  CopilotRequest,
  CopilotResponse,
  AedRequest,
  AedResponse,
  PriceBaseActiveStatus,
  PriceBaseInfo,
  PriceBankReference,
  PriceBankStats,
  PriceBankInventory,
  PriceSyncResult,
  PriceSyncSourceInfo,
  PriceSyncStatusResponse,
  OpenCompositionDetail,
  OpenCompositionListResponse,
  OpenCompositionSearchResponse,
  SystemBenchmarkResponse,
  ProjectDetail,
  ProjectFormatsResponse,
  ProjectListResponse,
  ProjectSummary,
  ConversationSummary,
  WorkspaceSearchResponse,
  ReviewDashboard,
  ReviewDetail,
  ReviewListResponse,
  NCListResponse,
  DigitalTwin,
  VisionModeItem,
  VisionStatusResponse,
  VisionAnalysisItem,
  VisionAnalyzeResponse,
  VisionAnalyzeProgress,
  VisionAnalysisListResponse,
  PciChecklistResponse,
  VisionReportRequest,
  VisionWorkspaceStatusResponse,
  WorkflowDashboardResponse,
  WorkflowJobItem,
  WorkflowProcessResponse,
  DeliveryPackageDetail,
  DeliveryPackageSummary,
  DeliveryPublishResponse,
  SheetTemplateItem,
  WorkflowProjectState,
  ActivityListResponse,
  DecisionListResponse,
  CompanyProfile,
  ExportBrandingConfig,
  AuthUser,
  AuthStatusResponse,
  AuthMeResponse,
  LoginResponse,
  UsersListResponse,
  UserRolesListResponse,
  SystemModulesResponse,
  ModulePermissionsMap,
  UserRoleDefinition,
  NetworkAccessConfig,
  QuickTunnelStatus,
  UserRole,
  ConsoleLogsResponse,
  ConsoleStatsResponse,
  ConsoleLiveResponse,
  UnloadResponse,
  MaintenanceConfigResponse,
  MaintenanceStatusResponse,
  MaintenanceInitResponse,
  MaintenanceBackupManifest,
  MaintenanceRestoreInspectResponse,
  MaintenanceRestoreResponse,
  DevServicesResponse,
  DevServiceActionResponse,
  DevStackStartResponse,
  ShellRunResponse,
  ShellHistoryItem,
} from "@/types/api";
import { seminfBundleFilesWithBasenames } from "@/lib/seminf-bundle";
import { getApiBaseUrl } from "@/lib/api-base";

function networkErrorMessage(err: unknown): string {
  const base = getApiBaseUrl();
  const raw = err instanceof Error ? err.message : String(err);
  if (/failed to fetch|networkerror|load failed/i.test(raw)) {
    const viaProxy = base.includes("/api-backend");
    return (
      `Não foi possível conectar à API (${base}). ` +
      (viaProxy
        ? "Confirme que `make api` está rodando no servidor e reinicie o frontend (`npm run dev`) após alterar next.config."
        : "Confirme que `make api` está rodando, o portproxy Windows está ativo e que você acessa o sistema pelo mesmo IP da rede (ex.: http://172.22.3.234:3000).")
    );
  }
  return raw;
}

async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (err) {
    throw new Error(networkErrorMessage(err));
  }
}

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

async function parseFetchError(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const json = JSON.parse(text) as { detail?: string | Array<{ msg?: string }> };
    if (typeof json.detail === "string") return json.detail;
    if (Array.isArray(json.detail)) {
      const parts = json.detail.map((d) => d.msg ?? "").filter(Boolean);
      if (parts.length) return parts.join("; ");
    }
  } catch {
    /* corpo não é JSON */
  }
  return text || `Erro HTTP ${response.status}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    if (
      response.status === 401 &&
      typeof window !== "undefined" &&
      !path.startsWith("/auth/login") &&
      !path.startsWith("/auth/status")
    ) {
      localStorage.removeItem("ia_auth_token");
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = `/login?next=${next}`;
      }
    }
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
    if (parsed.detail && typeof parsed.detail === "object" && "message" in parsed.detail) {
      const msg = (parsed.detail as { message?: string }).message;
      if (msg) return msg;
    }
    if (parsed.detail != null) return JSON.stringify(parsed.detail);
  } catch {
    /* texto puro */
  }
  if (/too many files/i.test(trimmed)) {
    return (
      "Limite de arquivos por requisição excedido. Reinicie a API (make api) e tente de novo — " +
      "acervos grandes são enviados automaticamente em lotes de 350 PDFs."
    );
  }
  return trimmed;
}

/** Download de arquivo (CSV, etc.) com headers de auth. */
export async function downloadApiFile(path: string, fallbackFilename: string): Promise<void> {
  const response = await apiFetch(`${getApiBaseUrl()}${path}`, {
    headers: getMultipartAuthHeaders(),
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(formatApiError(errorText, response.status));
  }
  const blob = await response.blob();
  const dispo = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";\n]+)"?/.exec(dispo);
  const filename = match?.[1] ?? fallbackFilename;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Download de texto (CSV gerado no cliente ou retornado pela API). */
export function downloadTextFile(content: string, filename: string, mime = "text/csv;charset=utf-8"): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function isSessionNotFoundError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return msg.includes("Sessão não encontrada") || msg.includes("Sessao nao encontrada");
}

const BUDGET_SESSION_RESTORED = "budget-session-restored";
const BUDGET_SESSION_STORAGE_KEY = "iaserver.budget.session";

let budgetSessionSnapshot: BudgetSessionResponse | null = null;

function persistBudgetSessionStorage(session: BudgetSessionResponse | null): void {
  if (typeof window === "undefined") return;
  try {
    if (!session) {
      sessionStorage.removeItem(BUDGET_SESSION_STORAGE_KEY);
      return;
    }
    sessionStorage.setItem(BUDGET_SESSION_STORAGE_KEY, JSON.stringify(session));
  } catch {
    /* quota / private mode */
  }
}

export async function restoreBudgetSessionFromStorage(): Promise<BudgetSessionResponse | null> {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(BUDGET_SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    const payload = JSON.parse(raw) as BudgetSessionResponse;
    if (!payload?.rows?.length && !payload?.items?.length) return null;
    const restored = await request<BudgetSessionResponse>("/pricing/budget/restore", {
      method: "POST",
      body: JSON.stringify({ payload }),
    });
    budgetSessionSnapshot = restored;
    persistBudgetSessionStorage(restored);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(BUDGET_SESSION_RESTORED, { detail: restored }));
    }
    return restored;
  } catch {
    return null;
  }
}

export function syncBudgetSessionSnapshot(session: BudgetSessionResponse | null): void {
  budgetSessionSnapshot = session;
  persistBudgetSessionStorage(session);
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
  const response = await apiFetch(`${getApiBaseUrl()}/chat/stream`, {
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
  const response = await apiFetch(`${getApiBaseUrl()}/pricing/budget/generate/stream`, {
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

export async function* knowledgeIngestWebStream(
  body: {
    page_url: string;
    discipline?: string;
    content_type?: string;
    description_prefix?: string;
    max_files?: number;
    force?: boolean;
    auto_index?: boolean;
  },
  signal?: AbortSignal
): AsyncGenerator<{ type: string; data: unknown }> {
  const response = await apiFetch(`${getApiBaseUrl()}/knowledge/ingest-web/stream`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(formatApiError(errorText, response.status));
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
      const trimmed = block.trim();
      if (!trimmed || trimmed.startsWith(":")) continue;
      const event = parseSseBlock(trimmed);
      if (event) {
        yield { type: event.type, data: event.data };
      }
    }
  }

  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim());
    if (event) {
      yield { type: event.type, data: event.data };
    }
  }
}

async function* readSseStream(
  response: Response
): AsyncGenerator<{ type: string; data: unknown }> {
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
      const trimmed = block.trim();
      if (!trimmed || trimmed.startsWith(":")) continue;
      const event = parseSseBlock(trimmed);
      if (event) {
        yield { type: event.type, data: event.data };
      }
    }
  }
  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim());
    if (event) {
      yield { type: event.type, data: event.data };
    }
  }
}

export async function knowledgeIngestWebWithProgress(
  body: {
    page_url: string;
    discipline?: string;
    content_type?: string;
    description_prefix?: string;
    max_files?: number;
    force?: boolean;
    auto_index?: boolean;
  },
  onProgress: (progress: WebIngestProgress) => void,
  signal?: AbortSignal
): Promise<KnowledgeWebIngestResponse> {
  for await (const event of knowledgeIngestWebStream(body, signal)) {
    if (event.type === "progress") {
      onProgress(event.data as WebIngestProgress);
    } else if (event.type === "done") {
      return event.data as KnowledgeWebIngestResponse;
    } else if (event.type === "error") {
      const payload = event.data as { error?: string };
      throw new Error(payload.error || "Erro na importação web");
    }
  }
  throw new Error("Importação encerrada sem resultado");
}

export async function* knowledgeIngestNormsStream(
  body: {
    files: File[];
    force?: boolean;
    use_ai_fallback?: boolean;
    mark_edition_outdated?: boolean;
    auto_index?: boolean;
  },
  signal?: AbortSignal
): AsyncGenerator<{ type: string; data: unknown }> {
  const formData = new FormData();
  for (const file of body.files) {
    formData.append("files", file);
  }
  formData.append("force", body.force ? "true" : "false");
  formData.append("use_ai_fallback", body.use_ai_fallback ? "true" : "false");
  formData.append("mark_edition_outdated", body.mark_edition_outdated ? "true" : "false");
  formData.append("auto_index", body.auto_index !== false ? "true" : "false");

  const response = await apiFetch(`${getApiBaseUrl()}/knowledge/ingest-norms/stream`, {
    method: "POST",
    headers: getMultipartAuthHeaders(),
    body: formData,
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(formatApiError(errorText, response.status));
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
      const trimmed = block.trim();
      if (!trimmed || trimmed.startsWith(":")) continue;
      const event = parseSseBlock(trimmed);
      if (event) {
        yield { type: event.type, data: event.data };
      }
    }
  }

  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim());
    if (event) {
      yield { type: event.type, data: event.data };
    }
  }
}

export const NORM_BULK_UPLOAD_CHUNK = 350;

function chunkFiles<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    chunks.push(items.slice(i, i + size));
  }
  return chunks;
}

function mergeNormBulkReports(results: NormBulkIngestResponse[]): NormBulkIngestResponse {
  if (results.length === 1) return results[0];

  const merged: NormBulkIngestResponse = {
    total_files: 0,
    ingested: 0,
    skipped: 0,
    errors: [],
    audit_rows: [],
  };

  const csvParts: string[] = [];

  for (const result of results) {
    merged.total_files = (merged.total_files ?? 0) + (result.total_files ?? 0);
    merged.ingested = (merged.ingested ?? 0) + (result.ingested ?? 0);
    merged.skipped = (merged.skipped ?? 0) + (result.skipped ?? 0);
    merged.errors!.push(...(result.errors ?? []));
    if (result.audit_rows?.length) {
      merged.audit_rows!.push(...result.audit_rows);
    }
    if (result.report_csv) csvParts.push(result.report_csv);
    if (result.indexing && !merged.indexing) {
      merged.indexing = result.indexing;
    }
  }

  if (csvParts.length === 1) {
    merged.report_csv = csvParts[0];
  } else if (csvParts.length > 1) {
    const lines = csvParts[0].split("\n");
    for (let i = 1; i < csvParts.length; i++) {
      const batchLines = csvParts[i].split("\n");
      const dataStart = batchLines.findIndex((line) => line.startsWith("Arquivo,"));
      if (dataStart >= 0) {
        lines.push(...batchLines.slice(dataStart + 1).filter(Boolean));
      }
    }
    merged.report_csv = lines.join("\n");
  }

  merged.report_filename = results[results.length - 1]?.report_filename ?? "auditoria-importacao-nbr.csv";
  merged.classified_count = merged.audit_rows?.length ?? 0;
  return merged;
}

async function knowledgeIngestNormsSingleBatch(
  body: {
    files: File[];
    force?: boolean;
    use_ai_fallback?: boolean;
    mark_edition_outdated?: boolean;
    auto_index?: boolean;
  },
  onProgress: (progress: WebIngestProgress) => void,
  signal?: AbortSignal
): Promise<NormBulkIngestResponse> {
  for await (const event of knowledgeIngestNormsStream(body, signal)) {
    if (event.type === "progress") {
      onProgress(event.data as WebIngestProgress);
    } else if (event.type === "done") {
      return event.data as NormBulkIngestResponse;
    } else if (event.type === "error") {
      const payload = event.data as { error?: string };
      throw new Error(payload.error || "Erro na importação em lote de normas");
    }
  }
  throw new Error("Importação encerrada sem resultado");
}

export async function knowledgeIngestNormsWithProgress(
  body: {
    files: File[];
    force?: boolean;
    use_ai_fallback?: boolean;
    mark_edition_outdated?: boolean;
    auto_index?: boolean;
  },
  onProgress: (progress: WebIngestProgress) => void,
  signal?: AbortSignal
): Promise<NormBulkIngestResponse> {
  const { files, ...options } = body;

  if (files.length <= NORM_BULK_UPLOAD_CHUNK) {
    return knowledgeIngestNormsSingleBatch({ files, ...options }, onProgress, signal);
  }

  const chunks = chunkFiles(files, NORM_BULK_UPLOAD_CHUNK);
  const results: NormBulkIngestResponse[] = [];

  for (let index = 0; index < chunks.length; index += 1) {
    const isLast = index === chunks.length - 1;
    onProgress({
      phase: "upload",
      current: index + 1,
      total: chunks.length,
      percent: Math.round((index / chunks.length) * 25),
      message: `Enviando lote ${index + 1}/${chunks.length} (${chunks[index].length} PDFs)…`,
    });

    const result = await knowledgeIngestNormsSingleBatch(
      {
        ...options,
        files: chunks[index],
        auto_index: isLast ? options.auto_index !== false : false,
      },
      (progress) => {
        if (isLast && progress.phase === "index") {
          const indexCurrent = progress.current ?? 0;
          const indexTotal = Math.max(progress.total ?? 1, 1);
          onProgress({
            ...progress,
            phase: "index",
            percent: Math.min(99, Math.round(75 + (indexCurrent / indexTotal) * 25)),
            message: progress.message,
          });
          return;
        }

        const innerPct = (progress.percent ?? 0) / 100;
        if (isLast) {
          onProgress({
            ...progress,
            phase: "upload",
            percent: Math.min(74, Math.round(25 + innerPct * 50)),
            message: `Lote ${index + 1}/${chunks.length}: ${progress.message}`,
          });
          return;
        }

        const batchWeight = 25 / chunks.length;
        const batchBase = (index / chunks.length) * 25;
        onProgress({
          ...progress,
          phase: "upload",
          percent: Math.min(24, Math.round(batchBase + innerPct * batchWeight)),
          message: `Lote ${index + 1}/${chunks.length}: ${progress.message}`,
        });
      },
      signal
    );
    results.push(result);
  }

  return mergeNormBulkReports(results);
}

export async function* techSpecComposeStream(
  sessionId: string,
  body: {
    prompt?: string;
    mode?: "generate" | "edit";
    use_llm?: boolean;
    llm_model?: string;
  },
  signal?: AbortSignal
): AsyncGenerator<TechSpecStreamEvent> {
  const response = await apiFetch(
    `${getApiBaseUrl()}/pricing/budget/${sessionId}/tech-spec/compose/stream`,
    {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
      signal,
    }
  );

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
      if (event) yield event as TechSpecStreamEvent;
    }
  }
  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim());
    if (event) yield event as TechSpecStreamEvent;
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

  techSpecComposeStream,

  orchestrate(body: OrchestrateRequest): Promise<OrchestrateResponse> {
    return request<OrchestrateResponse>("/orchestrate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  copilot(body: CopilotRequest): Promise<CopilotResponse> {
    return request<CopilotResponse>("/copilot", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  aed(body: AedRequest): Promise<AedResponse> {
    return request<AedResponse>("/aed", {
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
    indexing?: {
      status?: string;
      chunks?: number;
      filename?: string;
      error?: string;
      hint?: string;
    }[];
  }> {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    const response = await apiFetch(`${getApiBaseUrl()}/projects/${projectId}/files`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: formData,
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(formatApiError(errorText, response.status));
    }
    return response.json();
  },

  deleteProjectFile(projectId: string, fileId: string): Promise<{ deleted: boolean; id: string }> {
    return request(`/projects/${projectId}/files/${fileId}`, { method: "DELETE" });
  },

  reindexProject(projectId: string): Promise<Record<string, unknown>> {
    return request(`/projects/${projectId}/reindex`, { method: "POST" });
  },

  reviewDashboard(projectId: string): Promise<ReviewDashboard> {
    return request<ReviewDashboard>(`/projects/${projectId}/review/dashboard`);
  },

  listReviews(projectId: string): Promise<ReviewListResponse> {
    return request<ReviewListResponse>(`/projects/${projectId}/review`);
  },

  startReview(
    projectId: string,
    body?: { parent_review_id?: string; enable_vision?: boolean }
  ): Promise<ReviewDetail> {
    return request<ReviewDetail>(`/projects/${projectId}/review/start`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    });
  },

  getReview(projectId: string, reviewId: string): Promise<ReviewDetail> {
    return request<ReviewDetail>(`/projects/${projectId}/review/${reviewId}`);
  },

  listReviewNCs(projectId: string, reviewId: string): Promise<NCListResponse> {
    return request<NCListResponse>(`/projects/${projectId}/review/${reviewId}/ncs`);
  },

  getDigitalTwin(projectId: string): Promise<DigitalTwin> {
    return request<DigitalTwin>(`/projects/${projectId}/digital-twin`);
  },

  exportReviewReport(projectId: string, reviewId: string, reportType: string): string {
    return `${getApiBaseUrl()}/projects/${projectId}/review/${reviewId}/export/${reportType}`;
  },

  visionStatus(): Promise<VisionStatusResponse> {
    return request<VisionStatusResponse>("/projects/vision/status");
  },

  visionWorkspaceStatus(): Promise<VisionWorkspaceStatusResponse> {
    return request<VisionWorkspaceStatusResponse>("/projects/vision/workspace-status");
  },

  visionModes(): Promise<{ modes: VisionModeItem[] }> {
    return request<{ modes: VisionModeItem[] }>("/projects/vision/modes");
  },

  listVisionAnalyses(projectId: string): Promise<VisionAnalysisListResponse> {
    return request<VisionAnalysisListResponse>(`/projects/${projectId}/vision/analyses`);
  },

  getPciChecklist(projectId: string): Promise<PciChecklistResponse> {
    return request<PciChecklistResponse>(`/projects/${projectId}/vision/pci-checklist`);
  },

  analyzeVision(
    projectId: string,
    body: {
      file_ids?: string[];
      mode?: string;
      extra_context?: string;
      skip_technical?: boolean;
    }
  ): Promise<VisionAnalyzeResponse> {
    return request<VisionAnalyzeResponse>(`/projects/${projectId}/vision/analyze`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async fetchProjectFilePreview(projectId: string, fileId: string): Promise<Blob> {
    const response = await apiFetch(
      `${getApiBaseUrl()}/projects/${projectId}/files/${fileId}/preview`,
      { headers: getAuthHeaders() }
    );
    if (!response.ok) {
      throw new Error(`Preview indisponível (${response.status})`);
    }
    return response.blob();
  },

  async analyzeVisionWithProgress(
    projectId: string,
    body: {
      file_ids?: string[];
      mode?: string;
      extra_context?: string;
      skip_technical?: boolean;
    },
    onProgress: (progress: VisionAnalyzeProgress) => void,
    onFileDone?: (item: VisionAnalysisItem) => void,
    signal?: AbortSignal
  ): Promise<VisionAnalyzeResponse> {
    const response = await apiFetch(`${getApiBaseUrl()}/projects/${projectId}/vision/analyze/stream`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(formatApiError(errorText, response.status));
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
        const trimmed = block.trim();
        if (!trimmed || trimmed.startsWith(":")) continue;

        let eventType = "message";
        let dataStr = "";
        for (const line of trimmed.split("\n")) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
        }
        if (!dataStr) continue;

        let data: unknown;
        try {
          data = JSON.parse(dataStr);
        } catch {
          continue;
        }

        if (eventType === "progress") {
          onProgress(data as VisionAnalyzeProgress);
        } else if (eventType === "file_done" && onFileDone) {
          const payload = data as { item: VisionAnalysisItem };
          onFileDone(payload.item);
        } else if (eventType === "done") {
          return data as VisionAnalyzeResponse;
        } else if (eventType === "error") {
          const payload = data as { error?: string };
          throw new Error(payload.error || "Erro na análise visual");
        }
      }
    }

    throw new Error("Stream encerrado sem resultado final");
  },

  async exportVisionReport(projectId: string, body: VisionReportRequest): Promise<void> {
    const response = await apiFetch(`${getApiBaseUrl()}/projects/${projectId}/vision/report`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const err = (await response.json()) as { detail?: string };
        if (err.detail) detail = err.detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] ?? `vision_report_${projectId}.docx`;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },

  searchWorkspace(q: string, limit = 30): Promise<WorkspaceSearchResponse> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return request<WorkspaceSearchResponse>(`/workspace/search?${params.toString()}`);
  },

  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  authStatus(): Promise<AuthStatusResponse> {
    return request<AuthStatusResponse>("/auth/status");
  },

  async authLogin(username: string, password: string): Promise<LoginResponse> {
    const response = await apiFetch(`${getApiBaseUrl()}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(formatApiError(errorText, response.status));
    }
    return response.json() as Promise<LoginResponse>;
  },

  authMe(): Promise<AuthMeResponse> {
    return request<AuthMeResponse>("/auth/me");
  },

  authUsers(): Promise<UsersListResponse> {
    return request<UsersListResponse>("/auth/users");
  },

  authRoles(): Promise<UserRolesListResponse> {
    return request<UserRolesListResponse>("/auth/roles");
  },

  authModules(): Promise<SystemModulesResponse> {
    return request<SystemModulesResponse>("/auth/modules");
  },

  authCreateRole(body: {
    slug: string;
    label: string;
    module_permissions?: ModulePermissionsMap;
  }): Promise<{ role: UserRoleDefinition }> {
    return request("/auth/roles", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  authCreateUser(body: {
    username: string;
    password: string;
    email?: string;
    full_name?: string;
    role?: UserRole;
    is_active?: boolean;
    module_permissions?: ModulePermissionsMap;
  }): Promise<{ user: AuthUser }> {
    return request("/auth/users", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  authUpdateUser(
    userId: string,
    body: Partial<{
      email: string;
      full_name: string;
      role: UserRole;
      is_active: boolean;
      password: string;
      module_permissions: ModulePermissionsMap;
    }>
  ): Promise<{ user: AuthUser }> {
    return request(`/auth/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  authDeactivateUser(userId: string): Promise<{ ok: boolean; user: AuthUser }> {
    return request(`/auth/users/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    });
  },

  systemNetworkAccess(): Promise<NetworkAccessConfig> {
    return request<NetworkAccessConfig>("/system/network-access");
  },

  systemUpdateNetworkAccess(body: Partial<{
    internal: Partial<NetworkAccessConfig["internal"]>;
    cloudflare: Partial<NetworkAccessConfig["cloudflare"]> & { tunnel_token?: string };
    cors_extra_origins: string[];
  }>): Promise<NetworkAccessConfig> {
    return request<NetworkAccessConfig>("/system/network-access", {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  systemQuickTunnelStatus(): Promise<QuickTunnelStatus> {
    return request<QuickTunnelStatus>("/system/network-access/quick-tunnel");
  },

  systemStartQuickTunnel(): Promise<QuickTunnelStatus> {
    return request<QuickTunnelStatus>("/system/network-access/quick-tunnel/start", {
      method: "POST",
    });
  },

  systemStopQuickTunnel(): Promise<QuickTunnelStatus> {
    return request<QuickTunnelStatus>("/system/network-access/quick-tunnel/stop", {
      method: "POST",
    });
  },

  modelsStatus(): Promise<ModelsStatusResponse> {
    return request<ModelsStatusResponse>("/models/status");
  },

  systemBenchmark(): Promise<SystemBenchmarkResponse> {
    return request<SystemBenchmarkResponse>("/system/benchmark");
  },

  systemCompanyProfile(): Promise<CompanyProfile> {
    return request<CompanyProfile>("/system/company-profile");
  },

  systemUpdateCompanyProfile(body: Partial<CompanyProfile>): Promise<CompanyProfile> {
    return request<CompanyProfile>("/system/company-profile", {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  systemCompanyLogoUrl(): string {
    return `${getApiBaseUrl()}/system/company-profile/logo`;
  },

  systemCompanyBrasaoUrl(): string {
    return `${getApiBaseUrl()}/system/company-profile/brasao`;
  },

  async systemUploadCompanyLogo(file: File): Promise<CompanyProfile> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiFetch(`${getApiBaseUrl()}/system/company-profile/logo`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: formData,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json();
  },

  async systemUploadCompanyBrasao(file: File): Promise<CompanyProfile> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiFetch(`${getApiBaseUrl()}/system/company-profile/brasao`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: formData,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json();
  },

  async systemExportBranding(): Promise<ExportBrandingConfig> {
    return request<ExportBrandingConfig>("/system/export-branding");
  },

  async systemUpdateExportBranding(body: {
    header_title?: string;
    header_line1?: string;
    header_line2?: string;
    header_line3?: string;
    footer_line1?: string;
    footer_line2?: string;
    show_logo?: boolean;
    show_brasao?: boolean;
  }): Promise<ExportBrandingConfig> {
    return request<ExportBrandingConfig>("/system/export-branding", {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  knowledgeOptions(): Promise<KnowledgeOptionsResponse> {
    return request<KnowledgeOptionsResponse>("/knowledge/options");
  },

  knowledgeCreateDocumentTypePreset(body: {
    id?: string;
    label: string;
    content_type: string;
    discipline: string;
    register_price_base?: boolean;
    register_budget_model?: boolean;
  }): Promise<DocumentTypePreset> {
    return request<DocumentTypePreset>("/knowledge/document-type-presets", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  knowledgeUpdateDocumentTypePreset(
    id: string,
    body: Partial<{
      label: string;
      content_type: string;
      discipline: string;
      register_price_base: boolean;
      register_budget_model: boolean;
    }>
  ): Promise<DocumentTypePreset> {
    return request<DocumentTypePreset>(`/knowledge/document-type-presets/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  knowledgeDeleteDocumentTypePreset(id: string): Promise<DocumentTypePreset> {
    return request<DocumentTypePreset>(`/knowledge/document-type-presets/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  knowledgeStats(): Promise<KnowledgeStatsResponse> {
    return request<KnowledgeStatsResponse>("/knowledge/stats");
  },

  knowledgeCatalog(limit = 50): Promise<KnowledgeCatalogResponse> {
    return request<KnowledgeCatalogResponse>(`/knowledge/catalog?limit=${limit}`);
  },

  async knowledgeIngest(formData: FormData): Promise<KnowledgeIngestResponse> {
    const response = await apiFetch(`${getApiBaseUrl()}/knowledge/ingest`, {
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

  knowledgeIngestWeb(body: {
    page_url: string;
    discipline?: string;
    content_type?: string;
    description_prefix?: string;
    max_files?: number;
    force?: boolean;
    auto_index?: boolean;
  }): Promise<{
    page_url: string;
    discovered: number;
    downloaded: number;
    ingested: number;
    skipped: number;
    errors: { stage?: string; error?: string; url?: string }[];
    files: Record<string, unknown>[];
    indexing?: Record<string, unknown>;
  }> {
    return request("/knowledge/ingest-web", {
      method: "POST",
      body: JSON.stringify(body),
    });
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

  knowledgeNormPacks(): Promise<NormPackListResponse> {
    return request<NormPackListResponse>("/knowledge/norm-packs");
  },

  knowledgeNormPackAnalyze(packId: string): Promise<NormPackAnalyzeResponse> {
    return request<NormPackAnalyzeResponse>(`/knowledge/norm-packs/${encodeURIComponent(packId)}/analyze`);
  },

  knowledgeNormPackIndex(packId: string, force = false): Promise<NormPackIndexResponse> {
    return request<NormPackIndexResponse>(`/knowledge/norm-packs/${encodeURIComponent(packId)}/index`, {
      method: "POST",
      body: JSON.stringify({ force }),
    });
  },

  knowledgeNormPackPreview(packId: string, nbrCode?: string): Promise<NormPackPreviewResponse> {
    const qs = nbrCode ? `?nbr_code=${encodeURIComponent(nbrCode)}` : "";
    return request<NormPackPreviewResponse>(
      `/knowledge/norm-packs/${encodeURIComponent(packId)}/preview${qs}`
    );
  },

  downloadNormPackGapCsv(packId: string): Promise<void> {
    return downloadApiFile(
      `/knowledge/norm-packs/${encodeURIComponent(packId)}/gap.csv`,
      `gap-nbr-${packId}.csv`
    );
  },

  downloadDeliveryNormGapsCsv(projectId: string, packageId: string): Promise<void> {
    return downloadApiFile(
      `/projects/${encodeURIComponent(projectId)}/workflow/packages/${encodeURIComponent(packageId)}/norm-gaps.csv`,
      "pendencias-normativas-projeto.csv"
    );
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
    return `${getApiBaseUrl()}/pricing/budget/${sessionId}/export`;
  },

  pricingExportXlsxUrl(sessionId: string, docType: string): string {
    return `${getApiBaseUrl()}/pricing/budget/${sessionId}/export/xlsx/${docType}`;
  },

  pricingExportPdfUrl(sessionId: string, docType: string): string {
    return `${getApiBaseUrl()}/pricing/budget/${sessionId}/export/pdf/${docType}`;
  },

  pricingExportLogoUrl(sessionId: string): string {
    return `${getApiBaseUrl()}/pricing/budget/${sessionId}/export/logo`;
  },

  async pricingExportBranding(sessionId: string): Promise<{
    header_title?: string;
    header_line1?: string;
    header_line2?: string;
    header_line3?: string;
    footer_line1?: string;
    footer_line2?: string;
    show_logo?: boolean;
    has_logo?: boolean;
  }> {
    return request(`/pricing/budget/${sessionId}/export/branding`);
  },

  async pricingUpdateExportBranding(
    sessionId: string,
    body: {
      header_title?: string;
      header_line1?: string;
      header_line2?: string;
      header_line3?: string;
      footer_line1?: string;
      footer_line2?: string;
      show_logo?: boolean;
    }
  ): Promise<{ export_branding: Record<string, unknown>; session: BudgetSessionResponse }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/export/branding`, {
        method: "PATCH",
        body: JSON.stringify(body),
      })
    );
  },

  async pricingUploadExportLogo(
    sessionId: string,
    file: File
  ): Promise<{ export_branding: Record<string, unknown>; session: BudgetSessionResponse }> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiFetch(`${getApiBaseUrl()}/pricing/budget/${sessionId}/export/logo`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: formData,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json();
  },

  async pricingUploadBase(provider: string, file: File): Promise<Record<string, unknown>> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiFetch(`${getApiBaseUrl()}/pricing/providers/${provider}/upload`, {
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

  pricingSyncStatus(): Promise<PriceSyncStatusResponse> {
    return request("/pricing/sync/status");
  },

  pricingSyncSources(): Promise<{ sources: PriceSyncSourceInfo[] }> {
    return request("/pricing/sync/sources");
  },

  pricingSyncCreateSource(body: {
    name: string;
    label: string;
    download_url?: string;
  }): Promise<{ source: { name: string; label: string; download_url: string; custom: boolean } }> {
    return request("/pricing/sync/sources", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  pricingSyncUpdateSourceConfig(
    name: string,
    body: { download_url?: string; label?: string }
  ): Promise<{ source: { name: string; label: string; download_url: string; custom: boolean } }> {
    return request(`/pricing/sync/sources/${encodeURIComponent(name)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  pricingSyncDeleteSource(name: string): Promise<{ deleted: string }> {
    return request(`/pricing/sync/sources/${encodeURIComponent(name)}`, { method: "DELETE" });
  },

  pricingSyncBank(reference?: string): Promise<PriceBankStats> {
    const qs = reference ? `?reference=${encodeURIComponent(reference)}` : "";
    return request(`/pricing/sync/bank${qs}`);
  },

  pricingSyncBankReferences(): Promise<{ references: PriceBankReference[] }> {
    return request("/pricing/sync/bank/references");
  },

  pricingSyncBankInventory(): Promise<PriceBankInventory> {
    return request("/pricing/sync/bank/inventory");
  },

  pricingSyncSetActiveReference(reference: string): Promise<{ active_reference: string }> {
    return request("/pricing/sync/bank/active", {
      method: "POST",
      body: JSON.stringify({ reference }),
    });
  },

  pricingSyncDeleteReference(reference: string): Promise<{
    reference: string;
    index_removed: boolean;
    directory_removed: boolean;
    sync_files_removed: string[];
    faiss_purge?: { chunks_removed: number; remaining: number };
  }> {
    return request(`/pricing/sync/bank/references/${encodeURIComponent(reference)}`, {
      method: "DELETE",
    });
  },

  pricingPurgeSinapiFaiss(reference?: string): Promise<{
    index: string;
    reference: string | null;
    chunks_removed: number;
    remaining: number;
  }> {
    const params = reference ? `?reference=${encodeURIComponent(reference)}` : "";
    return request(`/pricing/sync/bank/faiss/sinapi${params}`, { method: "DELETE" });
  },

  pricingSyncOpenComposition(
    code: string,
    options?: { uf?: string; reference?: string }
  ): Promise<OpenCompositionDetail> {
    const params = new URLSearchParams();
    if (options?.uf) params.set("uf", options.uf);
    if (options?.reference) params.set("reference", options.reference);
    const qs = params.toString();
    return request(
      `/pricing/sync/bank/composition/${encodeURIComponent(code)}${qs ? `?${qs}` : ""}`
    );
  },

  pricingSyncListOpenCompositions(options?: {
    reference?: string;
    uf?: string;
    q?: string;
    offset?: number;
    limit?: number;
  }): Promise<OpenCompositionListResponse> {
    const params = new URLSearchParams();
    if (options?.reference) params.set("reference", options.reference);
    if (options?.uf) params.set("uf", options.uf);
    if (options?.q) params.set("q", options.q);
    if (options?.offset != null) params.set("offset", String(options.offset));
    if (options?.limit != null) params.set("limit", String(options.limit));
    const qs = params.toString();
    return request(`/pricing/sync/bank/open-compositions${qs ? `?${qs}` : ""}`);
  },

  pricingSyncSearchOpenCompositions(
    q: string,
    options?: { reference?: string; uf?: string; limit?: number; signal?: AbortSignal }
  ): Promise<OpenCompositionSearchResponse> {
    const params = new URLSearchParams();
    params.set("q", q);
    if (options?.reference) params.set("reference", options.reference);
    if (options?.uf) params.set("uf", options.uf);
    if (options?.limit != null) params.set("limit", String(options.limit));
    return request(`/pricing/sync/bank/open-compositions/search?${params.toString()}`, {
      signal: options?.signal,
    });
  },

  pricingSyncSource(
    source: string,
    body?: {
      uf?: string;
      year?: number;
      month?: number;
      index_faiss?: boolean;
      reload_providers?: boolean;
      set_active?: boolean;
    }
  ): Promise<PriceSyncResult> {
    return request(`/pricing/sync/${encodeURIComponent(source)}`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    });
  },

  async pricingSyncSourceWithProgress(
    source: string,
    body: {
      uf?: string;
      year?: number;
      month?: number;
      index_faiss?: boolean;
      reload_providers?: boolean;
      set_active?: boolean;
      download_all_regions?: boolean;
      skip_existing_ufs?: boolean;
    } | undefined,
    onProgress: (progress: WebIngestProgress) => void,
    signal?: AbortSignal
  ): Promise<PriceSyncResult> {
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/sync/${encodeURIComponent(source)}/stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(body ?? {}),
        signal,
      }
    );
    if (!response.ok) {
      throw new Error(await response.text());
    }
    for await (const event of readSseStream(response)) {
      if (event.type === "progress") {
        onProgress(event.data as WebIngestProgress);
      } else if (event.type === "done") {
        return event.data as PriceSyncResult;
      } else if (event.type === "error") {
        const payload = event.data as { error?: string };
        throw new Error(payload.error || "Erro na importação");
      }
    }
    throw new Error("Importação encerrada sem resultado");
  },

  async pricingSyncDpSeminfBundleWithProgress(
    source: string,
    files: {
      closed: File;
      openComd: File;
      openSemd: File;
    },
    options: {
      uf?: string;
      year?: number;
      month?: number;
      index_faiss?: boolean;
      reload_providers?: boolean;
      set_active?: boolean;
    } | undefined,
    onProgress: (progress: WebIngestProgress) => void,
    signal?: AbortSignal
  ): Promise<PriceSyncResult> {
    const params = new URLSearchParams();
    if (options?.uf) params.set("uf", options.uf);
    if (options?.year != null) params.set("year", String(options.year));
    if (options?.month != null) params.set("month", String(options.month));
    if (options?.index_faiss === false) params.set("index_faiss", "false");
    if (options?.reload_providers === false) params.set("reload_providers", "false");
    if (options?.set_active === false) params.set("set_active", "false");
    const qs = params.toString();
    const safeFiles = seminfBundleFilesWithBasenames(files);
    const formData = new FormData();
    formData.append("closed_file", safeFiles.closed);
    formData.append("open_comd_file", safeFiles.openComd);
    formData.append("open_semd_file", safeFiles.openSemd);
    onProgress({
      phase: "upload",
      percent: 2,
      current: 0,
      total: 3,
      message: "Enviando planilhas…",
    });
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/sync/${encodeURIComponent(source)}/upload/bundle/stream${qs ? `?${qs}` : ""}`,
      {
        method: "POST",
        headers: getMultipartAuthHeaders(),
        body: formData,
        signal,
      }
    );
    if (!response.ok) {
      throw new Error(await parseFetchError(response));
    }
    for await (const event of readSseStream(response)) {
      if (event.type === "progress") {
        onProgress(event.data as WebIngestProgress);
      } else if (event.type === "done") {
        return event.data as PriceSyncResult;
      } else if (event.type === "error") {
        const payload = event.data as { error?: string };
        throw new Error(payload.error || "Erro no upload em lote");
      }
    }
    throw new Error("Upload em lote encerrado sem resultado");
  },

  pricingSyncRefreshSeminfPrices(
    source: string,
    body: {
      reference: string;
      sinapi_reference: string;
      uf?: string;
      set_active?: boolean;
    }
  ): Promise<{
    status: string;
    reference: string;
    parent_reference?: string;
    sinapi_reference: string;
    uf: string;
    compositions_updated: number;
    items_updated: number;
    items_missing_price: number;
    warnings: string[];
  }> {
    return request(`/pricing/sync/${encodeURIComponent(source)}/refresh-prices`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async pricingSyncUploadWithProgress(
    source: string,
    file: File,
    options: {
      uf?: string;
      year?: number;
      month?: number;
      index_faiss?: boolean;
      reload_providers?: boolean;
      set_active?: boolean;
      download_all_regions?: boolean;
      skip_existing_ufs?: boolean;
    } | undefined,
    onProgress: (progress: WebIngestProgress) => void,
    signal?: AbortSignal
  ): Promise<PriceSyncResult> {
    const params = new URLSearchParams();
    if (options?.uf) params.set("uf", options.uf);
    if (options?.year != null) params.set("year", String(options.year));
    if (options?.month != null) params.set("month", String(options.month));
    if (options?.index_faiss === false) params.set("index_faiss", "false");
    if (options?.reload_providers === false) params.set("reload_providers", "false");
    if (options?.set_active === false) params.set("set_active", "false");
    const qs = params.toString();
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/sync/${encodeURIComponent(source)}/upload/stream${qs ? `?${qs}` : ""}`,
      {
        method: "POST",
        headers: getMultipartAuthHeaders(),
        body: formData,
        signal,
      }
    );
    if (!response.ok) {
      throw new Error(await response.text());
    }
    for await (const event of readSseStream(response)) {
      if (event.type === "progress") {
        onProgress(event.data as WebIngestProgress);
      } else if (event.type === "done") {
        return event.data as PriceSyncResult;
      } else if (event.type === "error") {
        const payload = event.data as { error?: string };
        throw new Error(payload.error || "Erro no upload");
      }
    }
    throw new Error("Upload encerrado sem resultado");
  },

  async pricingSyncUpload(
    source: string,
    file: File,
    options?: {
      uf?: string;
      index_faiss?: boolean;
      reload_providers?: boolean;
      set_active?: boolean;
    }
  ): Promise<PriceSyncResult> {
    const params = new URLSearchParams();
    if (options?.uf) params.set("uf", options.uf);
    if (options?.index_faiss === false) params.set("index_faiss", "false");
    if (options?.reload_providers === false) params.set("reload_providers", "false");
    if (options?.set_active === false) params.set("set_active", "false");
    const qs = params.toString();
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/sync/${encodeURIComponent(source)}/upload${qs ? `?${qs}` : ""}`,
      {
        method: "POST",
        headers: getMultipartAuthHeaders(),
        body: formData,
      }
    );
    if (!response.ok) {
      const text = await response.text();
      try {
        const parsed = JSON.parse(text) as { detail?: string | { message?: string; code?: string } };
        const detail = parsed.detail;
        if (typeof detail === "object" && detail?.message) {
          throw new Error(detail.message);
        }
        if (typeof detail === "string") {
          throw new Error(detail);
        }
      } catch (e) {
        if (e instanceof Error && e.message !== text) throw e;
      }
      throw new Error(text || `Erro HTTP ${response.status}`);
    }
    return response.json();
  },

  pricingImportPpd(file?: File): Promise<BudgetSessionResponse> {
    if (file) {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch(`${getApiBaseUrl()}/pricing/budget/import-ppd`, {
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
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/bases/import?name=${encodeURIComponent(name)}`,
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

  pricingListSkeletons(): Promise<{ items: BudgetSkeleton[]; count: number }> {
    return request("/pricing/budget/skeletons");
  },

  pricingGetSkeleton(id: string): Promise<BudgetSkeleton> {
    return request(`/pricing/budget/skeletons/${encodeURIComponent(id)}`);
  },

  pricingCreateSkeleton(body: {
    name: string;
    description?: string;
    obra_type?: string;
    etapas?: BudgetSkeletonEtapa[];
  }): Promise<BudgetSkeleton> {
    return request("/pricing/budget/skeletons", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  pricingUpdateSkeleton(
    id: string,
    body: Partial<{
      name: string;
      description: string;
      obra_type: string;
      etapas: BudgetSkeletonEtapa[];
    }>
  ): Promise<BudgetSkeleton> {
    return request(`/pricing/budget/skeletons/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  pricingDeleteSkeleton(id: string): Promise<{ deleted: string }> {
    return request(`/pricing/budget/skeletons/${encodeURIComponent(id)}`, { method: "DELETE" });
  },

  pricingNewFromSkeleton(
    skeletonId: string,
    options?: { projeto?: string; obraType?: string }
  ): Promise<BudgetSessionResponse> {
    const params = new URLSearchParams({ skeleton_id: skeletonId });
    if (options?.projeto) params.set("projeto", options.projeto);
    if (options?.obraType) params.set("obra_type", options.obraType);
    return request(`/pricing/budget/new-from-skeleton?${params}`, { method: "POST" });
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
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/budget/import-project?${params}`,
      { method: "POST", headers: getMultipartAuthHeaders(), body: formData }
    );
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  pricingListSaved(projectId?: string): Promise<{ items: BudgetSummary[] }> {
    const params = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    return request(`/pricing/budget/saved${params}`);
  },

  pricingGetSaved(id: string): Promise<BudgetSessionResponse> {
    return request(`/pricing/budget/saved/${id}`);
  },

  pricingSaveBudget(body: {
    title?: string;
    input_text?: string;
    project_id?: string | null;
    payload: BudgetSessionResponse;
  }): Promise<BudgetSessionResponse> {
    return request("/pricing/budget/saved", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  pricingUpdateSaved(
    id: string,
    body: {
      title?: string;
      input_text?: string;
      project_id?: string | null;
      payload: BudgetSessionResponse;
    }
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
    limit = 15,
    options?: { sessionId?: string; sourcePriority?: string[] }
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
      body: JSON.stringify({
        query,
        limit,
        ...(options?.sessionId ? { session_id: options.sessionId } : {}),
        ...(options?.sourcePriority?.length ? { source_priority: options.sourcePriority } : {}),
      }),
    });
  },

  pricingUpdateProject(
    sessionId: string,
    body: Record<string, string | undefined | BudgetPriceBaseSelection[] | undefined>
  ): Promise<BudgetSessionResponse> {
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

  pricingGetTechSpec(sessionId: string): Promise<{ tech_spec: TechSpecDocument | null }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/tech-spec`)
    );
  },

  pricingUpdateTechSpec(
    sessionId: string,
    body: Partial<TechSpecDocument>
  ): Promise<{ tech_spec: TechSpecDocument; session: BudgetSessionResponse }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/tech-spec`, {
        method: "PUT",
        body: JSON.stringify(body),
      })
    );
  },

  pricingClearTechSpec(
    sessionId: string
  ): Promise<{ tech_spec: null; session: BudgetSessionResponse }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/tech-spec`, {
        method: "DELETE",
      })
    );
  },

  pricingExportTechSpecUrl(sessionId: string): string {
    return `${getApiBaseUrl()}/pricing/budget/${sessionId}/tech-spec/export`;
  },

  pricingExportTechSpecPdfUrl(sessionId: string): string {
    return `${getApiBaseUrl()}/pricing/budget/${sessionId}/tech-spec/export/pdf`;
  },

  async pricingImportModelTemplate(file: File, sessionId?: string): Promise<BudgetSessionResponse & { imported_etapas?: number }> {
    const form = new FormData();
    form.append("file", file);
    const params = new URLSearchParams();
    if (sessionId) params.set("session_id", sessionId);
    const qs = params.toString();
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/budget/import-model-template${qs ? `?${qs}` : ""}`,
      { method: "POST", headers: getMultipartAuthHeaders(), body: form }
    );
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Erro HTTP ${response.status}`);
    }
    return response.json();
  },

  consoleLogs(limit = 50): Promise<ConsoleLogsResponse> {
    return request<ConsoleLogsResponse>(`/console/logs?limit=${limit}`);
  },

  consoleStats(): Promise<ConsoleStatsResponse> {
    return request<ConsoleStatsResponse>("/console/stats");
  },

  consoleLive(): Promise<ConsoleLiveResponse> {
    return request<ConsoleLiveResponse>("/console/live");
  },

  async *consoleLiveStream(signal?: AbortSignal): AsyncGenerator<ConsoleLiveResponse> {
    const response = await apiFetch(`${getApiBaseUrl()}/console/live/stream`, {
      headers: getAuthHeaders(),
      signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Erro HTTP ${response.status}`);
    }

    for await (const event of readSseStream(response)) {
      if (event.type === "live") {
        yield event.data as ConsoleLiveResponse;
      }
    }
  },

  consoleCancelJob(jobId: string): Promise<{ ok: boolean; job_id: string }> {
    return request(`/console/jobs/${jobId}/cancel`, { method: "POST" });
  },

  consoleUnloadModel(model: string): Promise<UnloadResponse> {
    return request<UnloadResponse>("/console/ollama/unload", {
      method: "POST",
      body: JSON.stringify({ model }),
    });
  },

  consoleUnloadAllModels(): Promise<UnloadResponse> {
    return request<UnloadResponse>("/console/ollama/unload-all", { method: "POST" });
  },

  projectActivity(projectId: string, limit = 100): Promise<ActivityListResponse> {
    return request<ActivityListResponse>(`/projects/${projectId}/activity?limit=${limit}`);
  },

  projectDecisions(projectId: string, limit = 50): Promise<DecisionListResponse> {
    return request<DecisionListResponse>(`/projects/${projectId}/decisions?limit=${limit}`);
  },

  workflowDashboard(): Promise<WorkflowDashboardResponse> {
    return request<WorkflowDashboardResponse>("/workflow/dashboard");
  },

  projectWorkflow(projectId: string): Promise<WorkflowProjectState> {
    return request<WorkflowProjectState>(`/projects/${projectId}/workflow`);
  },

  initProjectWorkflow(projectId: string, empresaId?: string): Promise<{ initialized: boolean }> {
    const qs = empresaId ? `?empresa_id=${encodeURIComponent(empresaId)}` : "";
    return request(`/projects/${projectId}/workflow/init${qs}`, { method: "POST" });
  },

  processProjectWorkflow(
    projectId: string,
    options?: { sync?: boolean; force?: boolean },
  ): Promise<WorkflowProcessResponse> {
    const params = new URLSearchParams();
    if (options?.sync) params.set("sync", "true");
    if (options?.force) params.set("force", "true");
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request(`/projects/${projectId}/workflow/process${qs}`, { method: "POST" });
  },

  workflowArtifactHref(pathOrKey: string): string {
    if (pathOrKey.startsWith("http://") || pathOrKey.startsWith("https://")) {
      return pathOrKey;
    }
    if (pathOrKey.startsWith("/workflow/")) {
      return `${getApiBaseUrl()}${pathOrKey}`;
    }
    return `${getApiBaseUrl()}/workflow/artifacts/download?key=${encodeURIComponent(pathOrKey)}`;
  },

  // --- Wizard de Entrega (Fase 3) ---

  sheetTemplates(): Promise<{ formatos: string[]; items: SheetTemplateItem[] }> {
    return request("/workflow/sheet-templates");
  },

  listDeliveryPackages(projectId: string): Promise<{ total: number; items: DeliveryPackageSummary[] }> {
    return request(`/projects/${projectId}/workflow/packages`);
  },

  createDeliveryPackage(projectId: string, titulo?: string): Promise<DeliveryPackageDetail> {
    return request(`/projects/${projectId}/workflow/packages`, {
      method: "POST",
      body: JSON.stringify({ titulo: titulo ?? null }),
    });
  },

  getDeliveryPackage(projectId: string, packageId: string): Promise<DeliveryPackageDetail> {
    return request(`/projects/${projectId}/workflow/packages/${packageId}`);
  },

  updateDeliveryPackage(
    projectId: string,
    packageId: string,
    data: Partial<{
      titulo: string;
      codigo_emissao: string;
      formato_padrao: string;
      orientacao_padrao: string;
      template_id: string | null;
      stamp_id: string | null;
      observacoes: string;
    }>,
  ): Promise<DeliveryPackageDetail> {
    return request(`/projects/${projectId}/workflow/packages/${packageId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  updateDeliverySelection(
    projectId: string,
    packageId: string,
    fileIds: string[],
  ): Promise<DeliveryPackageDetail> {
    return request(`/projects/${projectId}/workflow/packages/${packageId}/selection`, {
      method: "PUT",
      body: JSON.stringify({ file_ids: fileIds }),
    });
  },

  analyzeDeliveryPackage(projectId: string, packageId: string): Promise<DeliveryPackageDetail> {
    return request(`/projects/${projectId}/workflow/packages/${packageId}/analyze`, {
      method: "POST",
    });
  },

  updateDeliveryItem(
    projectId: string,
    packageId: string,
    itemId: string,
    data: Partial<{ codigo_aprovado: string; selected: boolean; formato: string; escala: string }>,
  ): Promise<DeliveryPackageDetail> {
    return request(`/projects/${projectId}/workflow/packages/${packageId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  publishDeliveryPackage(projectId: string, packageId: string): Promise<DeliveryPublishResponse> {
    return request(`/projects/${projectId}/workflow/packages/${packageId}/publish`, {
      method: "POST",
    });
  },

  workflowJob(jobId: string): Promise<WorkflowJobItem> {
    return request<WorkflowJobItem>(`/workflow/jobs/${jobId}`);
  },

  projectWorkflowJobs(projectId: string, limit = 20): Promise<{ total: number; items: WorkflowJobItem[] }> {
    return request(`/projects/${projectId}/workflow/jobs?limit=${limit}`);
  },

  workflowArtifactDownloadUrl(storageKey: string): string {
    return `${getApiBaseUrl()}/workflow/artifacts/download?key=${encodeURIComponent(storageKey)}`;
  },

  maintenanceStatus(): Promise<MaintenanceStatusResponse> {
    return request<MaintenanceStatusResponse>("/maintenance/status");
  },

  maintenanceConfig(): Promise<MaintenanceConfigResponse> {
    return request<MaintenanceConfigResponse>("/maintenance/config");
  },

  maintenanceUpdateConfig(body: Partial<MaintenanceConfigResponse>): Promise<MaintenanceConfigResponse> {
    return request<MaintenanceConfigResponse>("/maintenance/config", {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  maintenanceInitFolders(): Promise<MaintenanceInitResponse> {
    return request<MaintenanceInitResponse>("/maintenance/init-folders", { method: "POST" });
  },

  maintenanceHistory(limit = 20): Promise<{ items: MaintenanceBackupManifest[] }> {
    return request(`/maintenance/history?limit=${limit}`);
  },

  maintenanceBackup(targets: string[]): Promise<MaintenanceBackupManifest> {
    return request<MaintenanceBackupManifest>("/maintenance/backup", {
      method: "POST",
      body: JSON.stringify({ targets }),
    });
  },

  maintenanceStamps(includeDrive = true): Promise<{ stamps: string[] }> {
    return request(`/maintenance/stamps?include_drive=${includeDrive}`);
  },

  maintenanceRestoreInspect(stamp: string, fromDrive = true): Promise<MaintenanceRestoreInspectResponse> {
    return request(`/maintenance/restore/${encodeURIComponent(stamp)}/inspect?from_drive=${fromDrive}`);
  },

  maintenanceRestore(body: {
    stamp: string;
    targets: string[];
    from_drive?: boolean;
    dry_run?: boolean;
  }): Promise<MaintenanceRestoreResponse> {
    return request<MaintenanceRestoreResponse>("/maintenance/restore", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  devopsServices(): Promise<DevServicesResponse> {
    return request<DevServicesResponse>("/devops/services");
  },

  devopsStartService(serviceId: string): Promise<DevServiceActionResponse> {
    return request<DevServiceActionResponse>(`/devops/services/${serviceId}/start`, {
      method: "POST",
    });
  },

  devopsStopService(serviceId: string): Promise<DevServiceActionResponse> {
    return request<DevServiceActionResponse>(`/devops/services/${serviceId}/stop`, {
      method: "POST",
    });
  },

  devopsServiceLogs(serviceId: string, lines = 80): Promise<{ log: string }> {
    return request(`/devops/services/${serviceId}/logs?lines=${lines}`);
  },

  devopsStartCoreStack(): Promise<DevStackStartResponse> {
    return request<DevStackStartResponse>("/devops/stack/start-core", { method: "POST" });
  },

  devopsShellRun(command: string, cwd?: string, timeoutSec = 120): Promise<ShellRunResponse> {
    return request<ShellRunResponse>("/devops/shell/run", {
      method: "POST",
      body: JSON.stringify({ command, cwd, timeout_sec: timeoutSec }),
    });
  },

  devopsShellHistory(limit = 30): Promise<{ items: ShellHistoryItem[] }> {
    return request(`/devops/shell/history?limit=${limit}`);
  },
};

export { getApiBaseUrl, BUDGET_SESSION_RESTORED };
