import type {
  ChatAttachmentsUploadResponse,
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
  BdiEditalProfile,
  BdiTcuComponents,
  BudgetAuditEntry,
  BudgetGenerateRequest,
  BudgetPriceBaseSelection,
  BudgetSessionResponse,
  BudgetSkeleton,
  BudgetSkeletonEtapa,
  BudgetStreamEvent,
  BudgetSummary,
  BudgetRevisionItem,
  BudgetBaselineCompare,
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
  InspectionReport,
  InspectionReportGenerateProgress,
  InspectionAssayResult,
  InspectionAssayResultsView,
  InspectionVisualMemoryItem,
  InspectionVisualMemoryView,
  InspectionSignatureEvidence,
  InspectionReportParty,
  InspectionReportSolicitante,
  InspectionReportTemplate,
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
import {
  apiFetch,
  BudgetVersionConflictError,
  downloadApiFile,
  downloadTextFile,
  formatApiError,
  getApiBaseUrl,
  getAuthHeaders,
  getMultipartAuthHeaders,
  parseFetchError,
  request,
} from "./api/http";
import {
  BUDGET_SESSION_RESTORED,
  clearBudgetSessionSnapshot,
  isSessionNotFoundError,
  restoreBudgetSessionFromStorage,
  syncBudgetSessionSnapshot,
  withBudgetSessionRecovery,
} from "./api/budget-session";
import { budgetApi } from "./api/budget-api";
import { readSseStream } from "./api/sse";


export {
  BudgetVersionConflictError,
  formatApiError,
  downloadApiFile,
  downloadTextFile,
  isSessionNotFoundError,
  restoreBudgetSessionFromStorage,
  syncBudgetSessionSnapshot,
  clearBudgetSessionSnapshot,
};

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

  async chatUploadAttachments(files: File[]): Promise<ChatAttachmentsUploadResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    const response = await apiFetch(`${getApiBaseUrl()}/chat/attachments`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: formData,
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Erro HTTP ${response.status}`);
    }
    return response.json() as Promise<ChatAttachmentsUploadResponse>;
  },

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

  inspectionReportStatus(): Promise<{ gemini_available: boolean; gemini_model: string }> {
    return request("/inspection-reports/status");
  },

  inspectionReportTemplates(): Promise<{ items: InspectionReportTemplate[] }> {
    return request("/inspection-reports/templates");
  },

  createInspectionReportTemplate(
    body: Partial<InspectionReportTemplate> & { name: string }
  ): Promise<InspectionReportTemplate> {
    return request("/inspection-reports/templates", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  listInspectionReports(): Promise<{ items: InspectionReport[] }> {
    return request("/inspection-reports");
  },

  getInspectionReport(id: string): Promise<InspectionReport> {
    return request(`/inspection-reports/${id}`);
  },

  createInspectionReport(body: {
    title?: string;
    template_id?: string | null;
    user_prompt?: string;
    knowledge_mode?: string;
    suggest_instrumented_tests?: boolean;
    project_id?: string | null;
  }): Promise<InspectionReport> {
    return request("/inspection-reports", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  updateInspectionReport(
    id: string,
    body: {
      title?: string;
      template_id?: string | null;
      user_prompt?: string;
      knowledge_mode?: string;
      suggest_instrumented_tests?: boolean;
      project_id?: string | null;
      responsaveis_tecnicos?: InspectionReportParty[];
      responsaveis_imagens?: InspectionReportParty[];
      solicitante?: InspectionReportSolicitante;
      chapters?: Array<Record<string, unknown>>;
      photographic_report?: Array<Record<string, unknown>>;
      content_patch?: Record<string, unknown>;
    }
  ): Promise<InspectionReport> {
    return request(`/inspection-reports/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  async uploadInspectionReportAsset(
    reportId: string,
    file: File,
    opts?: { kind?: string; caption?: string }
  ): Promise<InspectionReport["assets"][number]> {
    const form = new FormData();
    form.append("file", file);
    if (opts?.kind) form.append("kind", opts.kind);
    if (opts?.caption) form.append("caption", opts.caption);
    const response = await apiFetch(`${getApiBaseUrl()}/inspection-reports/${reportId}/assets`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: form,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Upload falhou (${response.status})`);
    }
    return response.json();
  },

  deleteInspectionReport(id: string): Promise<{ ok: boolean }> {
    return request(`/inspection-reports/${id}`, { method: "DELETE" });
  },

  deleteInspectionReportAsset(reportId: string, assetId: string): Promise<{ ok: boolean }> {
    return request(`/inspection-reports/${reportId}/assets/${assetId}`, { method: "DELETE" });
  },

  async fetchInspectionReportAssetFile(reportId: string, assetId: string): Promise<Blob> {
    const response = await apiFetch(
      `${getApiBaseUrl()}/inspection-reports/${reportId}/assets/${assetId}/file`,
      { headers: getMultipartAuthHeaders() }
    );
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Falha ao carregar anexo (${response.status})`);
    }
    return response.blob();
  },

  generateInspectionReport(id: string): Promise<InspectionReport> {
    return request(`/inspection-reports/${id}/generate`, { method: "POST" });
  },

  async generateInspectionReportWithProgress(
    id: string,
    onProgress: (progress: InspectionReportGenerateProgress) => void,
    signal?: AbortSignal
  ): Promise<InspectionReport> {
    onProgress({
      phase: "prepare",
      percent: 8,
      message: "Abrindo stream de progresso…",
      report_id: id,
    });

    const response = await apiFetch(
      `${getApiBaseUrl()}/inspection-reports/${id}/generate/stream`,
      {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          Accept: "text/event-stream",
          "Cache-Control": "no-cache",
        },
        signal,
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(formatApiError(errorText, response.status));
    }

    for await (const event of readSseStream(response)) {
      if (event.type === "progress") {
        onProgress(event.data as InspectionReportGenerateProgress);
      } else if (event.type === "done") {
        const payload = event.data as { ok?: boolean; report?: InspectionReport };
        onProgress({
          phase: "done",
          percent: 100,
          message: "Laudo gerado com sucesso.",
          report_id: id,
        });
        if (payload.report) return payload.report;
        throw new Error("Geração concluída sem conteúdo do laudo");
      } else if (event.type === "error") {
        const payload = event.data as { message?: string; percent?: number; phase?: string };
        onProgress({
          phase: "error",
          percent: payload.percent ?? 100,
          message: payload.message || "Falha na geração do laudo",
          report_id: id,
        });
        throw new Error(payload.message || "Falha na geração do laudo");
      }
    }

    throw new Error("Stream encerrado sem resultado final");
  },

  correctInspectionReport(id: string, correction_prompt: string): Promise<InspectionReport> {
    return request(`/inspection-reports/${id}/correct`, {
      method: "POST",
      body: JSON.stringify({ correction_prompt }),
    });
  },

  async correctInspectionReportWithProgress(
    id: string,
    correction_prompt: string,
    onProgress: (progress: InspectionReportGenerateProgress) => void,
    signal?: AbortSignal
  ): Promise<InspectionReport> {
    onProgress({
      phase: "prepare",
      percent: 8,
      message: "Preparando correção…",
      report_id: id,
    });

    const response = await apiFetch(
      `${getApiBaseUrl()}/inspection-reports/${id}/correct/stream`,
      {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          Accept: "text/event-stream",
          "Cache-Control": "no-cache",
        },
        body: JSON.stringify({ correction_prompt }),
        signal,
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(formatApiError(errorText, response.status));
    }

    for await (const event of readSseStream(response)) {
      if (event.type === "progress") {
        onProgress(event.data as InspectionReportGenerateProgress);
      } else if (event.type === "done") {
        const payload = event.data as { ok?: boolean; report?: InspectionReport };
        onProgress({
          phase: "done",
          percent: 100,
          message: "Correção concluída.",
          report_id: id,
        });
        if (payload.report) return payload.report;
        throw new Error("Correção concluída sem conteúdo do laudo");
      } else if (event.type === "error") {
        const payload = event.data as { message?: string; percent?: number; phase?: string };
        onProgress({
          phase: "error",
          percent: payload.percent ?? 100,
          message: payload.message || "Falha na correção do laudo",
          report_id: id,
        });
        throw new Error(payload.message || "Falha na correção do laudo");
      }
    }

    throw new Error("Stream encerrado sem resultado final");
  },

  cancelInspectionReportGeneration(id: string): Promise<{ ok: boolean; message?: string }> {
    return request(`/inspection-reports/${id}/generate/cancel`, { method: "POST" });
  },

  updateInspectionReportAssetCaption(
    reportId: string,
    assetId: string,
    caption: string
  ): Promise<InspectionReport["assets"][number]> {
    return request(`/inspection-reports/${reportId}/assets/${assetId}`, {
      method: "PATCH",
      body: JSON.stringify({ caption }),
    });
  },

  getInspectionAssayResults(reportId: string): Promise<InspectionAssayResultsView> {
    return request(`/inspection-reports/${reportId}/assay-results`);
  },

  saveInspectionAssayResults(
    reportId: string,
    items: InspectionAssayResult[]
  ): Promise<InspectionAssayResultsView> {
    return request(`/inspection-reports/${reportId}/assay-results`, {
      method: "PUT",
      body: JSON.stringify({ items }),
    });
  },

  getInspectionVisualMemory(reportId: string): Promise<InspectionVisualMemoryView> {
    return request(`/inspection-reports/${reportId}/visual-memory`);
  },

  saveInspectionVisualMemory(
    reportId: string,
    items: InspectionVisualMemoryItem[]
  ): Promise<InspectionVisualMemoryView> {
    return request(`/inspection-reports/${reportId}/visual-memory`, {
      method: "PUT",
      body: JSON.stringify({ items }),
    });
  },

  getInspectionSignatureEvidence(reportId: string): Promise<InspectionSignatureEvidence> {
    return request(`/inspection-reports/${reportId}/signature-evidence`);
  },

  saveInspectionSignatureEvidence(
    reportId: string,
    body: {
      rt_signature_asset_ids?: Record<string, string>;
      notes?: string;
    }
  ): Promise<InspectionSignatureEvidence> {
    return request(`/inspection-reports/${reportId}/signature-evidence`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  lookupInspectionArt(body: {
    crea?: string;
    art?: string;
    art_protocolo?: string;
    uf?: string;
    probe?: boolean;
  }): Promise<{
    uf?: string | null;
    art?: string | null;
    art_protocolo?: string | null;
    art_url: string;
    sicar_url: string;
    source: string;
    live?: { reachable?: boolean; http_status?: number | null; error?: string } | null;
    consulted_at: string;
    notes?: string;
  }> {
    return request("/inspection-reports/art/lookup", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  claimInspectionReport(id: string): Promise<InspectionReport> {
    return request(`/inspection-reports/${id}/claim`, { method: "POST" });
  },

  assignInspectionReport(id: string, userId?: string): Promise<InspectionReport> {
    return request(`/inspection-reports/${id}/assign`, {
      method: "POST",
      body: JSON.stringify(userId ? { user_id: userId } : {}),
    });
  },

  backfillInspectionOrphans(userId?: string): Promise<{ assigned: number; user_id: string }> {
    return request("/inspection-reports/orphans/backfill", {
      method: "POST",
      body: JSON.stringify(userId ? { user_id: userId } : {}),
    });
  },

  inspectionReportExportChecklist(id: string): Promise<{
    ok: boolean;
    blocking: boolean;
    issues: Array<{ code: string; message: string }>;
    warnings: Array<{ code: string; message: string }>;
    ready_for_official_export: boolean;
  }> {
    return request(`/inspection-reports/${id}/export/checklist`);
  },

  inspectionReportExportDocxUrl(id: string, strict = false): string {
    return `${getApiBaseUrl()}/inspection-reports/${id}/export/docx${strict ? "?strict=true" : ""}`;
  },

  inspectionReportExportPdfUrl(id: string, strict = false): string {
    return `${getApiBaseUrl()}/inspection-reports/${id}/export/pdf${strict ? "?strict=true" : ""}`;
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

  async systemFetchCompanyLogo(): Promise<Blob> {
    const response = await apiFetch(`${getApiBaseUrl()}/system/company-profile/logo`, {
      headers: getMultipartAuthHeaders(),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.blob();
  },

  async systemFetchCompanyBrasao(): Promise<Blob> {
    const response = await apiFetch(`${getApiBaseUrl()}/system/company-profile/brasao`, {
      headers: getMultipartAuthHeaders(),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.blob();
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

  ...budgetApi,

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