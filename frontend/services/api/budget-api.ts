import type {
  BdiEditalProfile,
  BdiObraType,
  BdiTcuComponents,
  BdiValidationResult,
  CompliancePackPreview,
  BudgetAuditEntry,
  BudgetBaselineCompare,
  BudgetGenerateRequest,
  BudgetPriceBaseSelection,
  BudgetRevisionItem,
  BudgetSessionResponse,
  BudgetSkeleton,
  BudgetSkeletonEtapa,
  BudgetSummary,
  BudgetCompositionBatchResponse,
  OpenCompositionDetail,
  OpenCompositionListResponse,
  OpenCompositionSearchResponse,
  PriceMatchingCatalogHit,
  PriceMatchingJob,
  PriceMatchingRow,
  PriceBankInventory,
  PriceBankReference,
  PriceBankStats,
  PriceBaseActiveStatus,
  PriceBaseInfo,
  PriceSyncResult,
  PriceSyncSourceInfo,
  PriceSyncStatusResponse,
  PricingProvidersResponse,
  TechSpecDocument,
  WebIngestProgress,
} from "@/types/api";
import { seminfBundleFilesWithBasenames } from "@/lib/seminf-bundle";
import {
  apiFetch,
  getApiBaseUrl,
  getAuthHeaders,
  getMultipartAuthHeaders,
  parseFetchError,
  request,
} from "./http";
import { withBudgetSessionRecovery } from "./budget-session";
import { readSseStream } from "./sse";

export const budgetApi = {
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
        body: JSON.stringify({ obra_type: obraType, profile_id: "seminf_table" }),
      })
    );
  },

  pricingBdiProfiles(): Promise<{ profiles: BdiEditalProfile[] }> {
    return request("/pricing/bdi/profiles");
  },

  pricingUpdateBdiConfig(
    sessionId: string,
    body: {
      obra_type?: string;
      source?: string;
      profile_id?: string;
      label?: string;
      components_comd?: BdiTcuComponents;
      components_semd?: BdiTcuComponents;
    }
  ): Promise<BudgetSessionResponse> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request<BudgetSessionResponse>(`/pricing/budget/${sid}/bdi`, {
        method: "PATCH",
        body: JSON.stringify(body),
      })
    );
  },

  pricingBudgetAudit(sessionId: string): Promise<{
    session_id: string;
    items: BudgetAuditEntry[];
    session_entries: BudgetAuditEntry[];
    persisted_entries: BudgetAuditEntry[];
  }> {
    return request(`/pricing/budget/${sessionId}/audit`);
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

  pricingBudgetCompositionBatch(
    sessionId: string,
    options?: { backfill?: boolean }
  ): Promise<BudgetCompositionBatchResponse> {
    const params = new URLSearchParams();
    if (options?.backfill === false) params.set("backfill", "false");
    const qs = params.toString();
    return request<BudgetCompositionBatchResponse>(
      `/pricing/budget/${sessionId}/compositions/batch${qs ? `?${qs}` : ""}`
    );
  },

  pricingBudgetCompositionBackfill(
    sessionId: string
  ): Promise<{ session_id: string; budget_document_id: string; required: number; stored: number; fetched: number }> {
    return request(`/pricing/budget/${sessionId}/compositions/backfill`, { method: "POST" });
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

  pricingExportXlsmUrl(sessionId: string, sync = true): string {
    const q = sync ? "?sync=true" : "?sync=false";
    return `${getApiBaseUrl()}/pricing/budget/${sessionId}/export/xlsm${q}`;
  },

  pricingExportComplianceUrl(sessionId: string): string {
    return `${getApiBaseUrl()}/pricing/budget/${sessionId}/export/compliance-pack.json`;
  },

  async pricingBdiValidation(sessionId: string): Promise<BdiValidationResult> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/bdi/validation`)
    );
  },

  async pricingFetchCompliancePack(sessionId: string): Promise<CompliancePackPreview> {
    return withBudgetSessionRecovery(sessionId, async (sid) => {
      const response = await apiFetch(`${getApiBaseUrl()}/pricing/budget/${sid}/export/compliance-pack.json`, {
        headers: getMultipartAuthHeaders(),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      return response.json() as Promise<CompliancePackPreview>;
    });
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
    options?: { uf?: string; reference?: string; comparePrevious?: boolean }
  ): Promise<OpenCompositionDetail> {
    const params = new URLSearchParams();
    params.set("code", code);
    if (options?.uf) params.set("uf", options.uf);
    if (options?.reference) params.set("reference", options.reference);
    if (options?.comparePrevious === false) params.set("compare_previous", "false");
    return request(`/pricing/sync/bank/composition?${params.toString()}`);
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
      package_only?: boolean;
      portal_sync?: boolean;
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

  async pricingSyncOrseBundleWithProgress(
    files: {
      composicoes: File;
      insumos?: File;
      analitico?: File;
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
    const formData = new FormData();
    formData.append("composicoes_file", files.composicoes, files.composicoes.name);
    if (files.insumos) formData.append("insumos_file", files.insumos, files.insumos.name);
    if (files.analitico) formData.append("analitico_file", files.analitico, files.analitico.name);
    onProgress({
      phase: "upload",
      percent: 2,
      current: 0,
      total: 1 + (files.insumos ? 1 : 0) + (files.analitico ? 1 : 0),
      message: "Enviando export ORSE…",
    });
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/sync/orse/upload/bundle/stream${qs ? `?${qs}` : ""}`,
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
        throw new Error(payload.error || "Erro no upload ORSE");
      }
    }
    throw new Error("Importação ORSE encerrada sem resultado");
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

  pricingRestoreSession(payload: BudgetSessionResponse): Promise<BudgetSessionResponse> {
    return request<BudgetSessionResponse>("/pricing/budget/restore", {
      method: "POST",
      body: JSON.stringify({ payload }),
    });
  },

  pricingGetSaved(id: string): Promise<BudgetSessionResponse> {
    return request(`/pricing/budget/saved/${id}`);
  },

  pricingSaveBudget(body: {
    title?: string;
    input_text?: string;
    project_id?: string | null;
    expected_version?: number;
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
      expected_version?: number;
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

  pricingFreezeBaseline(budgetId: string): Promise<{ document: BudgetSummary; revision: Record<string, unknown> }> {
    return request(`/pricing/budget/saved/${budgetId}/freeze-baseline`, { method: "POST" });
  },

  pricingCreateRevision(
    budgetId: string,
    body?: { revision_label?: string }
  ): Promise<{ document: BudgetSummary; revision: Record<string, unknown>; session: BudgetSessionResponse }> {
    return request(`/pricing/budget/saved/${budgetId}/revision`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    });
  },

  pricingListRevisions(budgetId: string): Promise<{ items: BudgetRevisionItem[] }> {
    return request(`/pricing/budget/saved/${budgetId}/revisions`);
  },

  pricingBaselineCompare(budgetId: string): Promise<{
    baseline_document_id: string;
    revision: Record<string, unknown>;
    comparison: BudgetBaselineCompare;
  }> {
    return request(`/pricing/budget/saved/${budgetId}/baseline-compare`);
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
    body: Record<string, string | number | undefined | BudgetPriceBaseSelection[] | undefined>
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

  pricingAcquireBudgetLock(sessionId: string): Promise<{ session_id: string; expires_at?: string }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/lock`, { method: "POST" })
    );
  },

  pricingRenewBudgetLock(sessionId: string): Promise<{ session_id: string; renewed?: boolean }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/lock/renew`, { method: "POST" })
    );
  },

  pricingReleaseBudgetLock(sessionId: string): Promise<{ released: boolean }> {
    return withBudgetSessionRecovery(sessionId, (sid) =>
      request(`/pricing/budget/${sid}/lock`, { method: "DELETE" })
    );
  },

  priceMatchingImport(
    file: File,
    params: {
      bdi?: number;
      increase_index?: number;
      uf?: string;
      cliente?: string;
      obra?: string;
      price_bases?: BudgetPriceBaseSelection[];
    } = {}
  ): Promise<PriceMatchingJob> {
    const form = new FormData();
    form.append("file", file);
    const qs = new URLSearchParams();
    if (params.bdi != null) qs.set("bdi", String(params.bdi));
    if (params.increase_index != null) qs.set("increase_index", String(params.increase_index));
    if (params.uf) qs.set("uf", params.uf);
    if (params.cliente) qs.set("cliente", params.cliente);
    if (params.obra) qs.set("obra", params.obra);
    if (params.price_bases?.length) qs.set("price_bases", JSON.stringify(params.price_bases));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiFetch(`${getApiBaseUrl()}/pricing/budget/price-matching/import${suffix}`, {
      method: "POST",
      headers: getMultipartAuthHeaders(),
      body: form,
    }).then(async (r) => {
      if (!r.ok) throw new Error(await parseFetchError(r));
      return r.json() as Promise<PriceMatchingJob>;
    });
  },

  priceMatchingGetJob(jobId: string): Promise<PriceMatchingJob> {
    return request<PriceMatchingJob>(`/pricing/budget/price-matching/jobs/${jobId}`);
  },

  priceMatchingListJobs(limit = 50): Promise<{ jobs: PriceMatchingJob[] }> {
    return request<{ jobs: PriceMatchingJob[] }>(
      `/pricing/budget/price-matching/jobs?limit=${limit}`
    );
  },

  priceMatchingUpdateJob(
    jobId: string,
    body: Partial<
      Pick<PriceMatchingJob, "bdi" | "increase_index" | "cliente" | "obra" | "uf" | "price_bases">
    >
  ): Promise<PriceMatchingJob> {
    return request<PriceMatchingJob>(`/pricing/budget/price-matching/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  priceMatchingProcess(jobId: string, useLlm = true, asyncMode = true): Promise<PriceMatchingJob> {
    const qs = new URLSearchParams({
      use_llm: String(useLlm),
      async_mode: String(asyncMode),
    });
    return request<PriceMatchingJob>(
      `/pricing/budget/price-matching/jobs/${jobId}/process?${qs.toString()}`,
      { method: "POST" }
    );
  },

  priceMatchingAcceptRow(jobId: string, rowId: string): Promise<PriceMatchingRow> {
    return request<PriceMatchingRow>(
      `/pricing/budget/price-matching/jobs/${jobId}/rows/${rowId}/accept`,
      { method: "POST" }
    );
  },

  priceMatchingReplaceRow(
    jobId: string,
    rowId: string,
    body: {
      base: string;
      code: string;
      reference?: string;
      description?: string;
      unit?: string;
      price?: number;
      source?: string;
    }
  ): Promise<PriceMatchingRow> {
    return request<PriceMatchingRow>(
      `/pricing/budget/price-matching/jobs/${jobId}/rows/${rowId}/replace`,
      { method: "POST", body: JSON.stringify(body) }
    );
  },

  priceMatchingSearch(params: {
    q?: string;
    code?: string;
    base?: string;
    unit?: string;
    uf?: string;
    job_id?: string;
    limit?: number;
  }): Promise<{ results: PriceMatchingCatalogHit[]; count: number }> {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.code) qs.set("code", params.code);
    if (params.base) qs.set("base", params.base);
    if (params.unit) qs.set("unit", params.unit);
    if (params.uf) qs.set("uf", params.uf);
    if (params.job_id) qs.set("job_id", params.job_id);
    if (params.limit != null) qs.set("limit", String(params.limit));
    return request(`/pricing/budget/price-matching/search?${qs.toString()}`);
  },

  priceMatchingGenerateBudget(jobId: string): Promise<{
    session: BudgetSessionResponse;
    session_id: string;
    job_id: string;
    budget_id?: string;
    rows_imported: number;
    rows_matched: number;
    message: string;
  }> {
    return request(`/pricing/budget/price-matching/jobs/${jobId}/generate-budget`, {
      method: "POST",
    });
  },

  priceMatchingGetSession(
    jobId: string,
    options?: { syncPrices?: boolean }
  ): Promise<{
    session: BudgetSessionResponse;
    job: PriceMatchingJob;
    budget_id?: string;
  }> {
    const qs =
      options?.syncPrices === true
        ? "?sync_prices=true"
        : "";
    return request(`/pricing/budget/price-matching/jobs/${jobId}/session${qs}`);
  },

  priceMatchingSaveBudget(
    jobId: string,
    body: {
      payload?: BudgetSessionResponse;
      title?: string;
      expected_version?: number;
    } = {}
  ): Promise<{ session: BudgetSessionResponse; job_id: string; budget_id?: string }> {
    return request(`/pricing/budget/price-matching/jobs/${jobId}/save-budget`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  priceMatchingDeleteJob(
    jobId: string,
    deleteBudget = true
  ): Promise<{ deleted: boolean; job_id: string; budget_deleted: boolean }> {
    const qs = new URLSearchParams({ delete_budget: String(deleteBudget) });
    return request(`/pricing/budget/price-matching/jobs/${jobId}?${qs.toString()}`, {
      method: "DELETE",
    });
  },

  async priceMatchingExportExcel(jobId: string): Promise<Blob> {
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/budget/price-matching/jobs/${jobId}/export/excel`,
      {
      method: "POST",
      headers: getAuthHeaders(),
    }
    );
    if (!response.ok) throw new Error(await parseFetchError(response));
    return response.blob();
  },

  async priceMatchingExportPdf(jobId: string): Promise<Blob> {
    const response = await apiFetch(
      `${getApiBaseUrl()}/pricing/budget/price-matching/jobs/${jobId}/export/pdf`,
      {
      method: "POST",
      headers: getAuthHeaders(),
    }
    );
    if (!response.ok) throw new Error(await parseFetchError(response));
    return response.blob();
  },

};
