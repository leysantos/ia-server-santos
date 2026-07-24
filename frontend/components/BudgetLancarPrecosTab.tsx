"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ActionDialog from "@/components/ActionDialog";
import BudgetPriceBasesPanel from "@/components/BudgetPriceBasesPanel";
import { api, syncBudgetSessionSnapshot } from "@/services/api";
import type {
  BudgetPriceBaseSelection,
  PriceMatchingCatalogHit,
  PriceMatchingJob,
  PriceMatchingRow,
} from "@/types/api";
import { formatBrl } from "@/lib/open-composition-ui";
import { budgetBtn, budgetField, budgetFieldLabel, budgetInput } from "@/lib/budget-ui";
import { sourceLabel } from "@/lib/price-base-sources";
import { cn } from "@/lib/utils";

interface BudgetLancarPrecosPanelProps {
  onError?: (err: unknown, title?: string) => void;
  onSuccess?: (message: string, title?: string) => void;
  onImported?: (data: {
    session: import("@/types/api").BudgetSessionResponse;
    job: PriceMatchingJob;
    budget_id?: string;
    hierarchy_stats?: PriceMatchingJob["hierarchy_stats"];
  }) => void;
  onSessionUpdated?: (session: import("@/types/api").BudgetSessionResponse) => void;
  onJobUpdated?: (job: PriceMatchingJob) => void;
  onBudgetGenerated?: (data: {
    session: import("@/types/api").BudgetSessionResponse;
    job: PriceMatchingJob;
    budget_id?: string;
  }) => void;
  compactToolbar?: boolean;
  reloadJobId?: string | null;
  onReloadJobComplete?: () => void;
  workspaceJob?: PriceMatchingJob | null;
  workspaceSession?: import("@/types/api").BudgetSessionResponse | null;
  panelSyncToken?: number;
}

function confidenceClass(score: number | null | undefined): string {
  const pct = score == null ? 0 : score <= 1 ? score * 100 : score;
  if (pct >= 95) return "text-emerald-400";
  if (pct >= 80) return "text-amber-400";
  return "text-red-400";
}

function confidenceLabel(score: number | null | undefined): string {
  if (score == null) return "—";
  const pct = score <= 1 ? score * 100 : score;
  return `${pct.toFixed(0)}%`;
}

/** BDI no formulário é percentual (26,6); API/armazenamento usam decimal (0,266). */
function formatBdiPercentInput(decimal: number): string {
  return (decimal * 100).toLocaleString("pt-BR", { maximumFractionDigits: 4 });
}

function parseBdiPercentInput(value: string): number {
  const pct = parseFloat(value.replace(",", "."));
  if (Number.isNaN(pct)) return 0;
  return pct / 100;
}

export default function BudgetLancarPrecosPanel({
  onError,
  onSuccess,
  onImported,
  onSessionUpdated,
  onJobUpdated,
  onBudgetGenerated,
  compactToolbar,
  reloadJobId,
  onReloadJobComplete,
  workspaceJob,
  workspaceSession,
  panelSyncToken,
}: BudgetLancarPrecosPanelProps) {
  const [job, setJob] = useState<PriceMatchingJob | null>(null);
  const [bdi, setBdi] = useState("26,6");
  const [increaseIndex, setIncreaseIndex] = useState("1");
  const [uf, setUf] = useState("AM");
  const [cliente, setCliente] = useState("");
  const [obra, setObra] = useState("");
  const [importing, setImporting] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [exporting, setExporting] = useState<"excel" | "pdf" | null>(null);
  const [generatingBudget, setGeneratingBudget] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualRow, setManualRow] = useState<PriceMatchingRow | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [searchCode, setSearchCode] = useState("");
  const [searchBase, setSearchBase] = useState("");
  const [searchResults, setSearchResults] = useState<PriceMatchingCatalogHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [priceBases, setPriceBases] = useState<BudgetPriceBaseSelection[]>([]);
  const excelRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const rows = job?.rows ?? [];

  const processPercent = useMemo(() => {
    if (!processing && job?.status !== "processing") return 0;
    if (job?.process_percent != null) return Math.min(100, Math.round(job.process_percent));
    const total = job?.rows_total ?? rows.length;
    const done = job?.rows_processed ?? 0;
    if (total > 0) return Math.min(100, Math.round((done / total) * 100));
    return 0;
  }, [processing, job?.status, job?.process_percent, job?.rows_processed, job?.rows_total, rows.length]);

  const processRowsLabel = useMemo(() => {
    const total = job?.rows_total ?? rows.length;
    const done = job?.rows_processed ?? 0;
    return { done, total };
  }, [job?.rows_processed, job?.rows_total, rows.length]);

  const activePriceBases = useMemo(
    () => priceBases.filter((b) => b.enabled && b.reference),
    [priceBases]
  );

  const matchedCodesByItem = useMemo(() => {
    const map = new Map<string, string>();
    for (const row of rows) {
      if (row.item && row.codigo_base) map.set(row.item, row.codigo_base);
    }
    return map;
  }, [rows]);

  const applyJobToForm = useCallback(
    (data: PriceMatchingJob, session?: import("@/types/api").BudgetSessionResponse) => {
      setJob(data);
      if (data.bdi != null) setBdi(formatBdiPercentInput(data.bdi));
      if (data.increase_index != null) setIncreaseIndex(String(data.increase_index));
      if (data.uf) setUf(data.uf);
      setCliente(data.cliente ?? "");
      setObra(data.obra ?? "");
      const bases =
        data.price_bases?.length
          ? data.price_bases
          : session?.project?.price_bases?.length
            ? session.project.price_bases
            : [];
      setPriceBases(bases);
    },
    []
  );

  useEffect(() => {
    if (!panelSyncToken || !workspaceJob?.id) return;
    applyJobToForm(workspaceJob, workspaceSession ?? undefined);
  }, [panelSyncToken, workspaceJob, applyJobToForm]);

  useEffect(() => {
    if (!reloadJobId) return;
    const jobId = reloadJobId.split(":")[0];
    let cancelled = false;
    (async () => {
      try {
        const [sessionRes, jobData] = await Promise.all([
          api.priceMatchingGetSession(jobId, { syncPrices: false }),
          api.priceMatchingGetJob(jobId),
        ]);
        if (cancelled) return;
        const fullJob: PriceMatchingJob = {
          ...jobData,
          rows: jobData.rows ?? [],
          price_bases: jobData.price_bases?.length
            ? jobData.price_bases
            : sessionRes.session?.project?.price_bases ?? [],
        };
        applyJobToForm(fullJob, sessionRes.session);
        syncBudgetSessionSnapshot(sessionRes.session);
        onSessionUpdated?.(sessionRes.session);
        onImported?.({
          session: sessionRes.session,
          job: fullJob,
          budget_id:
            sessionRes.budget_id ??
            jobData.budget_document_id ??
            sessionRes.session?.db_id ??
            undefined,
        });
      } catch (e) {
        if (!cancelled) onError?.(e, "Recarregar orçamento");
      } finally {
        if (!cancelled) onReloadJobComplete?.();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadJobId, applyJobToForm, onError, onImported, onSessionUpdated, onReloadJobComplete]);

  useEffect(() => {
    if (reloadJobId || job?.id || priceBases.length > 0) return;
    api
      .pricingSyncBankReferences()
      .then((res) => {
        const first = res.references?.[0];
        if (!first?.reference) return;
        const source = (first.source || "sinapi").toLowerCase();
        setPriceBases([
          {
            source,
            label: sourceLabel(source, res.references ?? []),
            enabled: true,
            uf: (first.default_uf || uf || "SP").toUpperCase(),
            reference: first.reference,
          },
        ]);
      })
      .catch(() => {});
  }, [reloadJobId, job?.id, priceBases.length, uf]);

  const handlePriceBasesChange = useCallback(
    async (next: BudgetPriceBaseSelection[]) => {
      setPriceBases(next);
      if (!job?.id) return;
      try {
        const updatedJob = await api.priceMatchingUpdateJob(job.id, { price_bases: next });
        const mergedJob: PriceMatchingJob = { ...job, ...updatedJob, price_bases: next };
        setJob(mergedJob);
        onJobUpdated?.(mergedJob);

        const sessionId = workspaceSession?.session_id ?? job.session_id;
        if (sessionId) {
          const updatedSession = await api.pricingUpdateProject(sessionId, { price_bases: next });
          syncBudgetSessionSnapshot(updatedSession);
          onSessionUpdated?.(updatedSession);
        }
      } catch (e) {
        onError?.(e, "Atualizar bases de preços");
      }
    },
    [job, onError, onJobUpdated, onSessionUpdated, workspaceSession?.session_id]
  );

  const totals = useMemo(() => {
    const inc = parseFloat(increaseIndex.replace(",", ".")) || 1;
    let subtotal = 0;
    for (const row of rows) {
      const unit = (row.valor_unitario ?? 0) || (row.valor_unitario_base ?? 0) * inc;
      subtotal += unit * (row.quantidade ?? 0);
    }
    const bdiVal = parseBdiPercentInput(bdi);
    return { subtotal, grand: subtotal * (1 + bdiVal), bdi: bdiVal, increase: inc };
  }, [rows, bdi, increaseIndex]);

  const refreshSessionFromJob = useCallback(
    async (jobId: string) => {
      try {
        const res = await api.priceMatchingGetSession(jobId, { syncPrices: false });
        syncBudgetSessionSnapshot(res.session);
        onSessionUpdated?.(res.session);
        return res.session;
      } catch {
        return null;
      }
    },
    [onSessionUpdated]
  );

  const refreshJob = useCallback(async (jobId: string) => {
    const data = await api.priceMatchingGetJob(jobId);
    setJob(data);
    return data;
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startPolling = useCallback(
    (jobId: string) => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const data = await refreshJob(jobId);
          if (data.status === "done" || data.status === "draft") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setProcessing(false);
            if (data.status === "done") {
              void refreshSessionFromJob(jobId);
              onSuccess?.(
                `${data.rows_matched ?? 0} composições encontradas`,
                "Lançar Preços"
              );
            }
          }
        } catch {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setProcessing(false);
        }
      }, 800);
    },
    [refreshJob, refreshSessionFromJob, onSuccess]
  );

  useEffect(() => {
    if (job?.status === "processing" && job.id && !pollRef.current) {
      setProcessing(true);
      startPolling(job.id);
    }
  }, [job?.id, job?.status, startPolling]);

  const syncMeta = useCallback(async () => {
    if (!job?.id) return;
    const bdiVal = parseBdiPercentInput(bdi);
    const incVal = parseFloat(increaseIndex.replace(",", "."));
    try {
      await api.priceMatchingUpdateJob(job.id, {
        bdi: bdiVal,
        increase_index: Number.isNaN(incVal) ? 1 : incVal,
        cliente: cliente || undefined,
        obra: obra || undefined,
        uf,
        price_bases: priceBases,
      });
    } catch (e) {
      onError?.(e, "Atualizar parâmetros");
    }
  }, [job?.id, bdi, increaseIndex, cliente, obra, uf, priceBases, onError]);

  const handleImport = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".xlsx")) {
        onError?.("Use planilha Excel (.xlsx) com colunas Item, Descrição, Und e Quantidade.", "Importar planilha");
        return;
      }
      if (activePriceBases.length === 0) {
        onError?.("Adicione ao menos uma base de preços com período antes de importar.", "Importar planilha");
        return;
      }
      setImporting(true);
      try {
        const bdiVal = parseBdiPercentInput(bdi);
        const incVal = parseFloat(increaseIndex.replace(",", "."));
        const data = await api.priceMatchingImport(file, {
          bdi: bdiVal,
          increase_index: Number.isNaN(incVal) ? 1 : incVal,
          uf,
          cliente: cliente || undefined,
          obra: obra || undefined,
          price_bases: priceBases,
        });
        setJob(data);
        if (data.session) {
          syncBudgetSessionSnapshot(data.session);
          onImported?.({
            session: data.session,
            job: data,
            budget_id: data.budget_id ?? data.budget_document_id ?? undefined,
            hierarchy_stats: data.hierarchy_stats,
          });
          const stats = data.hierarchy_stats;
          const detail = stats
            ? `${stats.etapas} etapas, ${stats.sub_etapas} sub-etapas, ${stats.servicos} composições`
            : `${data.rows_total ?? data.rows?.length ?? 0} linhas`;
          onSuccess?.(`Orçamento importado — ${detail}`, "Importação");
        } else {
          onSuccess?.(`${data.rows_total ?? data.rows?.length ?? 0} linhas importadas`, "Importação");
        }
      } catch (e) {
        onError?.(e, "Importar planilha");
      } finally {
        setImporting(false);
      }
    },
    [bdi, increaseIndex, uf, cliente, obra, priceBases, activePriceBases.length, onError, onSuccess, onImported]
  );

  const handleProcess = useCallback(async () => {
    if (!job?.id) return;
    if (activePriceBases.length === 0) {
      onError?.("Adicione ao menos uma base de preços com período antes de processar.", "Lançar Preços");
      return;
    }
    setProcessing(true);
    try {
      await syncMeta();
      const data = await api.priceMatchingProcess(job.id, true, true);
      setJob({
        ...job,
        ...data,
        id: data.id ?? job.id,
        rows: data.rows ?? job.rows,
        rows_total: data.rows_total ?? job.rows_total,
        rows_processed: data.rows_processed ?? 0,
        process_percent: data.process_percent ?? 0,
        status: data.status ?? job.status,
      });
      if (data.status === "processing") {
        startPolling(job.id);
      } else {
        setProcessing(false);
        onSuccess?.(`${data.rows_matched ?? 0} composições encontradas`, "Lançar Preços");
        await refreshSessionFromJob(job.id);
      }
    } catch (e) {
      setProcessing(false);
      onError?.(e, "Processar preços");
    }
  }, [job, activePriceBases.length, syncMeta, startPolling, onError, onSuccess, refreshSessionFromJob]);

  const handleAccept = useCallback(
    async (row: PriceMatchingRow) => {
      if (!job?.id) return;
      try {
        await api.priceMatchingAcceptRow(job.id, row.id);
        await refreshJob(job.id);
        await refreshSessionFromJob(job.id);
      } catch (e) {
        onError?.(e, "Aceitar composição");
      }
    },
    [job?.id, refreshJob, refreshSessionFromJob, onError]
  );

  const runManualSearch = useCallback(async () => {
    const q = searchQ.trim();
    const code = searchCode.trim();
    if (!q && !code) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    try {
      const res = await api.priceMatchingSearch({
        q: q || undefined,
        code: code || undefined,
        base: searchBase || undefined,
        unit: manualRow?.unidade || undefined,
        uf,
        job_id: job?.id,
        limit: 30,
      });
      setSearchResults(res.results);
    } catch (e) {
      onError?.(e, "Pesquisa manual");
    } finally {
      setSearching(false);
    }
  }, [searchQ, searchCode, searchBase, manualRow?.unidade, uf, job?.id, onError]);

  const closeManualSearch = useCallback(() => {
    setManualOpen(false);
    setManualRow(null);
    setSearchResults([]);
    setSearchCode("");
  }, []);

  const handleSelectManual = useCallback(
    (hit: PriceMatchingCatalogHit) => {
      if (!job?.id || !manualRow) return;
      const jobId = job.id;
      const rowId = manualRow.id;
      closeManualSearch();
      void (async () => {
        try {
          await api.priceMatchingReplaceRow(jobId, rowId, {
            base: hit.base,
            code: hit.code,
            reference: hit.reference,
            description: hit.description,
            unit: hit.unit,
            price: hit.price,
            source: hit.source,
          });
          onSuccess?.(`Preço lançado — ${hit.base} ${hit.code}`, "Pesquisa manual");
          void refreshJob(jobId).then((data) => setJob(data));
          window.setTimeout(() => {
            void refreshSessionFromJob(jobId);
          }, 400);
        } catch (e) {
          onError?.(e, "Lançar composição");
        }
      })();
    },
    [job?.id, manualRow, refreshJob, refreshSessionFromJob, closeManualSearch, onError, onSuccess]
  );

  useEffect(() => {
    if (!manualOpen) return;
    const timer = window.setTimeout(() => {
      void runManualSearch();
    }, 350);
    return () => window.clearTimeout(timer);
  }, [manualOpen, searchQ, searchCode, searchBase, runManualSearch]);

  const handleGenerateBudget = useCallback(async () => {
    if (!job?.id) return;
    setGeneratingBudget(true);
    try {
      await syncMeta();
      const result = await api.priceMatchingGenerateBudget(job.id);
      const refreshed = await api.priceMatchingGetJob(job.id);
      const mergedJob: PriceMatchingJob = { ...job, ...refreshed, rows: refreshed.rows ?? job.rows ?? [] };
      setJob(mergedJob);
      syncBudgetSessionSnapshot(result.session);
      onSessionUpdated?.(result.session);
      onJobUpdated?.(mergedJob);
      onBudgetGenerated?.({
        session: result.session,
        job: mergedJob,
        budget_id: result.budget_id ?? result.session.db_id ?? undefined,
      });
      onSuccess?.(
        "Orçamento gerado com preços lançados — visualize nas abas sintético, analítico e cronograma",
        "Lançar Preços"
      );
    } catch (e) {
      onError?.(e, "Lançar Preços");
    } finally {
      setGeneratingBudget(false);
    }
  }, [job, syncMeta, onError, onSuccess, onSessionUpdated, onJobUpdated, onBudgetGenerated]);

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportExcel = async () => {
    if (!job?.id) return;
    setExporting("excel");
    try {
      await syncMeta();
      const blob = await api.priceMatchingExportExcel(job.id);
      downloadBlob(blob, `lancar_precos_${job.id.slice(0, 8)}.xlsx`);
    } catch (e) {
      onError?.(e, "Exportar Excel");
    } finally {
      setExporting(null);
    }
  };

  const handleExportPdf = async () => {
    if (!job?.id) return;
    setExporting("pdf");
    try {
      await syncMeta();
      const blob = await api.priceMatchingExportPdf(job.id);
      downloadBlob(blob, `lancar_precos_${job.id.slice(0, 8)}.pdf`);
    } catch (e) {
      onError?.(e, "Exportar PDF");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="rounded-xl border border-white/5 bg-surface-card/40 p-4">
        <h2 className="text-sm font-semibold text-slate-100">Lançar Preços</h2>
        <p className="mt-1 text-xs text-slate-400">
          Selecione as bases de preços e os períodos importados. O matching e a pesquisa manual usam
          somente essas bases. Importe a planilha Excel (.xlsx) com Item, Código (opcional), Descrição,
          Und e Quantidade — etapas e sub-etapas são preservadas na ordem da planilha.
        </p>

        <div className="mt-4">
          <BudgetPriceBasesPanel
            value={priceBases}
            disabled={importing || processing}
            onChange={(next) => void handlePriceBasesChange(next)}
          />
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Cliente</span>
            <input className={budgetInput} value={cliente} onChange={(e) => setCliente(e.target.value)} />
          </label>
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Obra</span>
            <input className={budgetInput} value={obra} onChange={(e) => setObra(e.target.value)} />
          </label>
          <label className={budgetField}>
            <span className={budgetFieldLabel}>BDI (%)</span>
            <input
              className={budgetInput}
              value={bdi}
              onChange={(e) => setBdi(e.target.value)}
              placeholder="26,6"
              inputMode="decimal"
            />
          </label>
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Índice acréscimo (ex. 1,2 = +20%)</span>
            <input className={budgetInput} value={increaseIndex} onChange={(e) => setIncreaseIndex(e.target.value)} />
          </label>
          <label className={budgetField}>
            <span className={budgetFieldLabel}>UF preços</span>
            <input className={budgetInput} value={uf} onChange={(e) => setUf(e.target.value.toUpperCase())} maxLength={2} />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <input
            ref={excelRef}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleImport(f);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            className={cn(budgetBtn, "bg-brand-600/20 text-brand-200 hover:bg-brand-600/30")}
            disabled={importing}
            onClick={() => excelRef.current?.click()}
          >
            {importing ? "Importando…" : "Importar planilha Excel"}
          </button>
          <button
            type="button"
            className={cn(budgetBtn, "bg-emerald-700/30 text-emerald-100 hover:bg-emerald-700/40")}
            disabled={!job?.rows?.length || processing}
            onClick={() => void handleProcess()}
          >
            {processing ? `Processando… ${processPercent}%` : "Processar Preços"}
          </button>
          <button
            type="button"
            className={cn(budgetBtn, "bg-surface-elevated text-slate-200 hover:bg-white/10")}
            disabled={!job?.id || exporting != null}
            onClick={() => void handleExportExcel()}
          >
            {exporting === "excel" ? "Exportando…" : "Exportar Excel"}
          </button>
          <button
            type="button"
            className={cn(budgetBtn, "bg-surface-elevated text-slate-200 hover:bg-white/10")}
            disabled={!job?.id || exporting != null}
            onClick={() => void handleExportPdf()}
          >
            {exporting === "pdf" ? "Exportando…" : "Exportar PDF"}
          </button>
          <button
            type="button"
            className={cn(budgetBtn, "bg-brand-600/30 text-brand-100 hover:bg-brand-600/40")}
            disabled={!job?.id || generatingBudget || !(job.rows_matched ?? 0)}
            onClick={() => void handleGenerateBudget()}
          >
            {generatingBudget ? "Gerando orçamento…" : "Lançar Preços"}
          </button>
        </div>

        {(processing || job?.status === "processing") && (
          <div className="mt-3 rounded-lg border border-emerald-500/20 bg-emerald-950/20 px-4 py-3">
            <div className="mb-2 flex items-center justify-between text-xs">
              <span className="font-medium text-emerald-100">Buscando composições nas bases de preço…</span>
              <span className="tabular-nums font-semibold text-emerald-300">{processPercent}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-[width] duration-300 ease-out"
                style={{ width: `${processPercent}%` }}
              />
            </div>
            <p className="mt-1.5 text-[11px] text-slate-500">
              {processRowsLabel.done} de {processRowsLabel.total} linhas processadas
            </p>
          </div>
        )}

        {job && (
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-400">
            <span>Status: {job.status}</span>
            {job.hierarchy_stats && (
              <span>
                Hierarquia: {job.hierarchy_stats.etapas} etapas · {job.hierarchy_stats.sub_etapas} sub-etapas ·{" "}
                {job.hierarchy_stats.servicos} composições
              </span>
            )}
            <span>Linhas matching: {job.rows_total ?? rows.length}</span>
            <span>Matched: {job.rows_matched ?? 0}</span>
            <span>Subtotal: {formatBrl(totals.subtotal)}</span>
            <span className="font-medium text-slate-200">Total c/ BDI: {formatBrl(totals.grand)}</span>
          </div>
        )}
      </div>

        {job?.hierarchy && job.hierarchy.length > 0 && (
          <div className="rounded-xl border border-white/5 bg-surface-card/30 p-3">
            <h3 className="text-xs font-semibold text-slate-200">Orçamento importado</h3>
            <p className="mt-1 text-[11px] text-slate-500">
              Colunas separadas: item, código, descrição, unidade e quantidade — na ordem do arquivo.
            </p>
            <div className="mt-2 max-h-56 overflow-auto rounded-lg border border-white/5">
              <table className="w-full min-w-[720px] border-collapse text-[11px]">
                <thead className="sticky top-0 bg-surface-card text-slate-400">
                  <tr>
                    <th className="border-b border-white/5 px-2 py-1.5 text-left">Item</th>
                    <th className="border-b border-white/5 px-2 py-1.5 text-left">Código</th>
                    <th className="border-b border-white/5 px-2 py-1.5 text-left">Descrição</th>
                    <th className="border-b border-white/5 px-2 py-1.5 text-center">Un.</th>
                    <th className="border-b border-white/5 px-2 py-1.5 text-right">Qtd.</th>
                    <th className="border-b border-white/5 px-2 py-1.5 text-center">Tipo</th>
                  </tr>
                </thead>
                <tbody>
                  {job.hierarchy.map((ln, idx) => {
                    const itemKey = String(ln.item ?? "");
                    const code =
                      matchedCodesByItem.get(itemKey) || String(ln.codigo ?? "") || "—";
                    return (
                    <tr key={`${ln.item}-${idx}`} className="border-b border-white/5">
                      <td className="px-2 py-1 font-mono text-slate-200">{itemKey}</td>
                      <td className="px-2 py-1 font-mono text-slate-400">{code}</td>
                      <td className="max-w-[280px] truncate px-2 py-1 text-slate-300" title={String(ln.descricao ?? "")}>
                        {String(ln.descricao ?? "")}
                      </td>
                      <td className="px-2 py-1 text-center text-slate-400">{String(ln.unidade ?? "") || "—"}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-slate-400">
                        {ln.quantidade != null && Number(ln.quantidade) !== 0
                          ? Number(ln.quantidade).toLocaleString("pt-BR", { maximumFractionDigits: 4 })
                          : "—"}
                      </td>
                      <td className="px-2 py-1 text-center text-slate-500">{String(ln.row_type ?? "")}</td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

      {!compactToolbar && (
      <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-white/5">
        <table className="w-full min-w-[1100px] border-collapse text-xs">
          <thead className="sticky top-0 bg-surface-card text-slate-400">
            <tr>
              <th className="border-b border-white/5 px-2 py-2 text-left">Item</th>
              <th className="border-b border-white/5 px-2 py-2 text-left">Código</th>
              <th className="border-b border-white/5 px-2 py-2 text-left">Descrição</th>
              <th className="border-b border-white/5 px-2 py-2 text-center">Un.</th>
              <th className="border-b border-white/5 px-2 py-2 text-right">Qtd.</th>
              <th className="border-b border-white/5 px-2 py-2 text-left">Descrição encontrada</th>
              <th className="border-b border-white/5 px-2 py-2">Base</th>
              <th className="border-b border-white/5 px-2 py-2 text-right">V. unit.</th>
              <th className="border-b border-white/5 px-2 py-2 text-right">V. total</th>
              <th className="border-b border-white/5 px-2 py-2">Conf.</th>
              <th className="border-b border-white/5 px-2 py-2">Ações</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={11} className="px-4 py-8 text-center text-slate-500">
                  Importe a planilha Excel para iniciar.
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                <td className="px-2 py-2 font-mono text-slate-200">{row.item || "—"}</td>
                <td className="px-2 py-2 font-mono text-[11px] text-slate-400">{row.codigo_base || "—"}</td>
                <td className="max-w-[220px] px-2 py-2 align-top text-slate-100">
                  <div className="truncate" title={row.descricao_original}>
                    {row.descricao_original}
                  </div>
                </td>
                <td className="px-2 py-2 text-center text-slate-400">{row.unidade || "—"}</td>
                <td className="px-2 py-2 text-right tabular-nums text-slate-400">
                  {row.quantidade?.toLocaleString("pt-BR", { maximumFractionDigits: 4 }) ?? "—"}
                </td>
                <td className="max-w-[220px] px-2 py-2 align-top text-slate-300">
                  {row.descricao_base || "—"}
                </td>
                <td className="px-2 py-2 text-center">{row.base || "—"}</td>
                <td className="px-2 py-2 text-right tabular-nums">{formatBrl(row.valor_unitario ?? 0)}</td>
                <td className="px-2 py-2 text-right tabular-nums">{formatBrl(row.valor_total ?? 0)}</td>
                <td className={cn("px-2 py-2 text-center font-medium", confidenceClass(row.score_confianca))}>
                  {confidenceLabel(row.score_confianca)}
                </td>
                <td className="px-2 py-2">
                  <div className="flex flex-col gap-1">
                    <button
                      type="button"
                      className={cn(budgetBtn, "h-8 min-h-8 px-2 text-[10px]")}
                      disabled={!row.codigo_base}
                      onClick={() => void handleAccept(row)}
                    >
                      Aceitar
                    </button>
                    <button
                      type="button"
                      className={cn(budgetBtn, "h-8 min-h-8 px-2 text-[10px]")}
                      onClick={() => {
                        setManualRow(row);
                        setSearchQ(row.descricao_original.slice(0, 80));
                        setSearchCode("");
                        setSearchBase("");
                        setSearchResults([]);
                        setManualOpen(true);
                      }}
                    >
                      Pesquisar
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}

      {manualOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeManualSearch();
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") closeManualSearch();
          }}
          role="presentation"
        >
          <div className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-xl border border-white/10 bg-surface-card shadow-xl">
            <div className="border-b border-white/5 p-4">
              <h3 className="text-sm font-semibold text-slate-100">Pesquisa manual de composição</h3>
              <p className="mt-1 text-xs text-slate-500">
                Busque por código ou descrição. Clique em um resultado para lançar o preço e fechar.
              </p>
              <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs">
                <p
                  className="min-w-0 flex-1 truncate text-slate-300"
                  title={manualRow?.descricao_original}
                >
                  {manualRow?.descricao_original}
                </p>
                {manualRow && (
                  <span className="shrink-0 tabular-nums text-slate-500">
                    <span className="text-slate-400">Un.</span> {manualRow.unidade || "—"}
                    <span className="mx-2 text-white/10">·</span>
                    <span className="text-slate-400">Qtd.</span>{" "}
                    {manualRow.quantidade?.toLocaleString("pt-BR", { maximumFractionDigits: 4 }) ?? "—"}
                  </span>
                )}
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-4">
                <input
                  className={budgetInput}
                  placeholder="Descrição"
                  value={searchQ}
                  onChange={(e) => setSearchQ(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void runManualSearch();
                  }}
                />
                <input
                  className={budgetInput}
                  placeholder="Código"
                  value={searchCode}
                  onChange={(e) => setSearchCode(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void runManualSearch();
                  }}
                />
                <select
                  className={budgetInput}
                  value={searchBase}
                  onChange={(e) => setSearchBase(e.target.value)}
                >
                  <option value="">Todas bases</option>
                  <option value="SEMINF">SEMINF</option>
                  <option value="SINAPI">SINAPI</option>
                  <option value="SICRO">SICRO</option>
                  <option value="ORSE">ORSE</option>
                </select>
                <button type="button" className={budgetBtn} disabled={searching} onClick={() => void runManualSearch()}>
                  {searching ? "…" : "Buscar"}
                </button>
              </div>
            </div>
            <div className="max-h-[50vh] overflow-auto p-2">
              {searchResults.map((hit) => (
                <button
                  key={`${hit.base}-${hit.code}-${hit.reference}`}
                  type="button"
                  className="mb-1 w-full cursor-pointer rounded-lg border border-white/5 px-3 py-2 text-left text-xs transition-colors hover:border-cyan-500/30 hover:bg-cyan-500/5"
                  onClick={() => handleSelectManual(hit)}
                >
                  <div className="font-medium text-slate-100">
                    {hit.base} · {hit.code}
                  </div>
                  <div className="text-slate-300">{hit.description}</div>
                  <div className="text-slate-500">
                    {hit.unit} · {formatBrl(hit.price)} · {hit.reference}
                  </div>
                </button>
              ))}
              {!searchResults.length && !searching && (
                <p className="p-4 text-center text-slate-500">
                  {searchQ.trim() || searchCode.trim()
                    ? "Nenhum resultado — tente outro código ou descrição"
                    : "Digite código ou descrição para buscar"}
                </p>
              )}
              {searching && (
                <p className="p-4 text-center text-slate-500">Buscando composições…</p>
              )}
            </div>
            <div className="border-t border-white/5 p-3 text-right">
              <button type="button" className={budgetBtn} onClick={closeManualSearch}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
