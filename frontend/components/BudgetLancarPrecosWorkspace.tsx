"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import BudgetAnaliticoTab from "@/components/BudgetAnaliticoTab";
import BudgetCurvaAbcTab from "@/components/BudgetCurvaAbcTab";
import BudgetCurvaSTab from "@/components/BudgetCurvaSTab";
import BudgetDadosTab from "@/components/BudgetDadosTab";
import BudgetEtapasPanel from "@/components/BudgetEtapasPanel";
import BudgetHistogramaTab from "@/components/BudgetHistogramaTab";
import BudgetLancarPrecosHistoricoTab from "@/components/BudgetLancarPrecosHistoricoTab";
import BudgetLancarPrecosPanel from "@/components/BudgetLancarPrecosTab";
import BudgetMemoryPanel from "@/components/BudgetMemoryPanel";
import BudgetSchedulePanel from "@/components/BudgetSchedulePanel";
import BudgetSpreadsheet from "@/components/BudgetSpreadsheet";
import BudgetTechSpecPanel from "@/components/BudgetTechSpecPanel";
import BudgetToolbar from "@/components/BudgetToolbar";
import LoadingSpinner from "@/components/LoadingSpinner";
import type { ProjectFormValues } from "@/components/BudgetProjectForm";
import type { CommercialFormValues } from "@/components/BudgetCommercialPanel";
import {
  api,
  BudgetVersionConflictError,
  clearBudgetSessionSnapshot,
  downloadApiFile,
  syncBudgetSessionSnapshot,
} from "@/services/api";
import type {
  BdiObraType,
  BudgetPriceBaseSelection,
  BudgetSessionResponse,
  BudgetSummary,
  PriceMatchingJob,
} from "@/types/api";
import {
  buildLancarPrecosUrl,
  parseLancarPrecosTab,
  persistLancarPrecosJob,
  persistLancarPrecosTab,
  type LancarPrecosTabId,
} from "@/lib/lancar-precos-state";
import { prefetchBudgetServiceCompositions } from "@/hooks/useBudgetServiceCompositions";
import { cn } from "@/lib/utils";

const TABS: { id: LancarPrecosTabId; label: string }[] = [
  { id: "lancar_precos", label: "Lançar Preços" },
  { id: "historico", label: "Histórico" },
  { id: "dados", label: "Dados do orçamento" },
  { id: "etapas", label: "Etapas e composições" },
  { id: "ppd", label: "Orç. Sintético" },
  { id: "analitico", label: "Orç. Analítico" },
  { id: "memoria", label: "Memória de cálculo" },
  { id: "cronograma", label: "Cronograma" },
  { id: "curva_abc", label: "Curva ABC" },
  { id: "curva_s", label: "Curva S" },
  { id: "histograma", label: "Histograma" },
  { id: "especificacao", label: "Especificação técnica" },
];

interface BudgetLancarPrecosWorkspaceProps {
  onError?: (err: unknown, title?: string) => void;
  onSuccess?: (message: string, title?: string) => void;
  onConfirmDelete?: (onConfirm: () => void) => void;
}

function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: LancarPrecosTabId; label: string }[];
  active: LancarPrecosTabId;
  onChange: (id: LancarPrecosTabId) => void;
}) {
  return (
    <div className="shrink-0 overflow-x-auto pb-0.5">
      <div
        className="inline-flex min-w-full flex-nowrap gap-0.5 rounded-xl bg-slate-900/70 p-1 ring-1 ring-slate-700/50"
        role="tablist"
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              "whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-all",
              active === tab.id
                ? "bg-cyan-500/15 text-cyan-100 shadow-sm ring-1 ring-cyan-500/40"
                : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function BudgetLancarPrecosWorkspace({
  onError,
  onSuccess,
  onConfirmDelete,
}: BudgetLancarPrecosWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [session, setSession] = useState<BudgetSessionResponse | null>(null);
  const [job, setJob] = useState<PriceMatchingJob | null>(null);
  const [activeTab, setActiveTabState] = useState<LancarPrecosTabId>(() =>
    parseLancarPrecosTab(searchParams.get("tab"))
  );
  const [activeDbId, setActiveDbId] = useState<string | null>(null);
  const [documentVersion, setDocumentVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exportingDoc, setExportingDoc] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [bdiTypes, setBdiTypes] = useState<BdiObraType[]>([]);
  const [obraType, setObraType] = useState("RF");
  const [sinapiImported, setSinapiImported] = useState(false);
  const [savedItems, setSavedItems] = useState<BudgetSummary[]>([]);
  const [reloadJobId, setReloadJobId] = useState<string | null>(null);
  const [panelSyncToken, setPanelSyncToken] = useState(0);
  const [panelResetToken, setPanelResetToken] = useState(0);
  const [historicoRefresh, setHistoricoRefresh] = useState(0);
  const restoreHandled = useRef(false);

  const syncUrlState = useCallback(
    (jobId: string | null, tab: LancarPrecosTabId) => {
      persistLancarPrecosJob(jobId);
      persistLancarPrecosTab(tab);
      router.replace(buildLancarPrecosUrl(jobId, tab), { scroll: false });
    },
    [router]
  );

  const setActiveTab = useCallback(
    (tab: LancarPrecosTabId) => {
      setActiveTabState(tab);
      syncUrlState(job?.id ?? null, tab);
    },
    [job?.id, syncUrlState]
  );

  const notifySuccess = useCallback(
    (message: string, title?: string) => {
      onSuccess?.(message, title);
      setHistoricoRefresh((n) => n + 1);
    },
    [onSuccess]
  );

  const budgetTabsEnabled = !!session;

  const sessionHasBudgetTree = useCallback((s: BudgetSessionResponse | null) => {
    if (!s) return false;
    return (s.items?.length ?? 0) > 0 || (s.rows?.length ?? 0) > 0;
  }, []);

  useEffect(() => {
    api.pricingBdiTypes().then((r) => {
      setBdiTypes(r.types);
      setObraType(r.default);
    }).catch(() => {});
    api.pricingListSaved().then((r) => setSavedItems(r.items ?? [])).catch(() => {});
    api.pricingSyncBankReferences()
      .then((r) => setSinapiImported((r.references ?? []).length > 0))
      .catch(() => setSinapiImported(false));
  }, []);

  const handleImported = useCallback(
    (
      data: {
        session: BudgetSessionResponse;
        job: PriceMatchingJob;
        budget_id?: string;
      },
      options?: { tab?: LancarPrecosTabId }
    ) => {
      setSession(data.session);
      setJob(data.job);
      syncBudgetSessionSnapshot(data.session);
      setActiveDbId(data.budget_id ?? data.session.db_id ?? null);
      if (data.session.document_version != null) {
        setDocumentVersion(data.session.document_version);
      }
      const nextTab = options?.tab ?? "lancar_precos";
      setActiveTabState(nextTab);
      syncUrlState(data.job.id ?? null, nextTab);
      setHistoricoRefresh((n) => n + 1);
    },
    [syncUrlState]
  );

  const handleOpenHistoricoJob = useCallback(
    async (jobId: string, options?: { tab?: LancarPrecosTabId }) => {
      setActiveTabState(options?.tab ?? "lancar_precos");
      setLoading(true);
      try {
        const jobData = await api.priceMatchingGetJob(jobId);
        const partialJob: PriceMatchingJob = {
          ...jobData,
          rows: jobData.rows ?? [],
        };
        setJob(partialJob);
        setPanelSyncToken(Date.now());
        setLoading(false);

        const sessionRes = await api.priceMatchingGetSession(jobId, { syncPrices: false });
        const fullJob: PriceMatchingJob = {
          ...partialJob,
          price_bases: partialJob.price_bases?.length
            ? partialJob.price_bases
            : sessionRes.session?.project?.price_bases ?? [],
        };
        handleImported(
          {
            session: sessionRes.session,
            job: fullJob,
            budget_id:
              sessionRes.budget_id ??
              jobData.budget_document_id ??
              sessionRes.session?.db_id ??
              undefined,
          },
          { tab: options?.tab }
        );
        setPanelSyncToken(Date.now());
        if (!sessionHasBudgetTree(sessionRes.session) && (fullJob.rows?.length ?? 0) > 0) {
          void api
            .priceMatchingGetSession(jobId, { syncPrices: true })
            .then((hydrated) => {
              handleImported(
                {
                  session: hydrated.session,
                  job: fullJob,
                  budget_id:
                    hydrated.budget_id ??
                    jobData.budget_document_id ??
                    hydrated.session?.db_id ??
                    undefined,
                },
                { tab: options?.tab }
              );
              setPanelSyncToken(Date.now());
            })
            .catch(() => {});
        }
      } catch (e) {
        onError?.(e, "Abrir orçamento");
        setLoading(false);
      }
    },
    [handleImported, onError, sessionHasBudgetTree]
  );

  useEffect(() => {
    if (restoreHandled.current) return;
    restoreHandled.current = true;
    const jobId = searchParams.get("job");
    const tab = parseLancarPrecosTab(searchParams.get("tab"));
    if (jobId) {
      void handleOpenHistoricoJob(jobId, { tab }).finally(() => setRestoring(false));
    } else {
      setActiveTabState(tab);
      setRestoring(false);
    }
  }, [searchParams, handleOpenHistoricoJob]);

  const handleReloadJobComplete = useCallback(() => {
    setReloadJobId(null);
  }, []);

  const handleReprocessHistoricoJob = useCallback(
    async (jobId: string) => {
      try {
        setLoading(true);
        const current = await api.priceMatchingGetJob(jobId);
        const rowCount = current.rows_total ?? current.rows?.length ?? 0;
        const data = await api.priceMatchingProcess(jobId, true, rowCount > 50);
        setJob(data);
        setReloadJobId(`${jobId}:${Date.now()}`);
        setPanelSyncToken(Date.now());
        setActiveTab("lancar_precos");
        const sessionRes = await api.priceMatchingGetSession(jobId, { syncPrices: true });
        setSession(sessionRes.session);
        syncBudgetSessionSnapshot(sessionRes.session);
        setActiveDbId(sessionRes.budget_id ?? sessionRes.session.db_id ?? null);
        notifySuccess(`${data.rows_matched ?? 0} composições encontradas`, "Reprocessar preços");
        setHistoricoRefresh((n) => n + 1);
      } catch (e) {
        onError?.(e, "Reprocessar preços");
      } finally {
        setLoading(false);
      }
    },
    [onError, notifySuccess]
  );

  const handleDeleteHistoricoJob = useCallback(
    (jobId: string) => {
      onConfirmDelete?.(async () => {
        try {
          setLoading(true);
          await api.priceMatchingDeleteJob(jobId, true);
          if (job?.id === jobId) {
            setJob(null);
            setSession(null);
            setActiveDbId(null);
            setDocumentVersion(null);
            syncUrlState(null, "lancar_precos");
          }
          setHistoricoRefresh((n) => n + 1);
          onSuccess?.("Orçamento removido do histórico", "Excluir");
        } catch (e) {
          onError?.(e, "Excluir");
        } finally {
          setLoading(false);
        }
      });
    },
    [job?.id, onConfirmDelete, onError, onSuccess, syncUrlState]
  );

  const handleSessionUpdated = useCallback((next: BudgetSessionResponse) => {
    setSession(next);
    syncBudgetSessionSnapshot(next);
    if (next.db_id) setActiveDbId(next.db_id);
    if (next.document_version != null) setDocumentVersion(next.document_version);
  }, []);

  useEffect(() => {
    if (!session) return;
    syncBudgetSessionSnapshot(session);
  }, [session]);

  const handleJobUpdated = useCallback((next: PriceMatchingJob) => {
    setJob(next);
    syncUrlState(next.id ?? null, activeTab);
  }, [activeTab, syncUrlState]);

  const handleBudgetGenerated = useCallback(
    (data: {
      session: BudgetSessionResponse;
      job: PriceMatchingJob;
      budget_id?: string;
    }) => {
      handleImported(data, { tab: "ppd" });
      // Prefetch leve após sync em background (snapshots ainda gravando)
      window.setTimeout(() => {
        void prefetchBudgetServiceCompositions(data.session);
      }, 2500);
    },
    [handleImported]
  );

  const hydrateSessionInBackground = useCallback(
    (jobId: string) => {
      void api
        .priceMatchingGetSession(jobId, { syncPrices: true })
        .then((sessionRes) => {
          handleSessionUpdated(sessionRes.session);
          setPanelSyncToken(Date.now());
          void prefetchBudgetServiceCompositions(sessionRes.session);
        })
        .catch(() => {});
    },
    [handleSessionUpdated]
  );

  const handleTabChange = useCallback(
    (tab: LancarPrecosTabId) => {
      setActiveTab(tab);
      if (
        tab !== "lancar_precos" &&
        tab !== "historico" &&
        job?.id &&
        session &&
        !sessionHasBudgetTree(session)
      ) {
        hydrateSessionInBackground(job.id);
      }
    },
    [job?.id, session, sessionHasBudgetTree, hydrateSessionInBackground, setActiveTab]
  );

  const handleNewOrcamento = useCallback(() => {
    setSession(null);
    setJob(null);
    setActiveDbId(null);
    setDocumentVersion(null);
    setReloadJobId(null);
    setLoading(false);
    setSaving(false);
    clearBudgetSessionSnapshot();
    syncUrlState(null, "lancar_precos");
    setActiveTabState("lancar_precos");
    setPanelSyncToken(0);
    setPanelResetToken((n) => n + 1);
  }, [syncUrlState]);

  const handleOpenBudgetModule = useCallback(
    (targetJob: PriceMatchingJob) => {
      const budgetId = targetJob.budget_document_id;
      if (!budgetId) {
        onError?.(
          "Este orçamento ainda não foi vinculado ao módulo completo. Use «Lançar Preços» e Salvar.",
          "Abrir módulo de orçamento"
        );
        return;
      }
      router.push(`/budget?open=${budgetId}&tab=etapas`);
    },
    [onError, router]
  );

  const handleCellEdit = useCallback(
    async (rowId: string, field: string, value: number | string, code?: string) => {
      if (!session) throw new Error("Sem sessão");
      return api.pricingUpdateCell(session.session_id, { row_id: rowId, field, value, code });
    },
    [session]
  );

  const persistBudget = useCallback(async () => {
    if (!session || !job?.id) return;
    setSaving(true);
    try {
      const saved = await api.priceMatchingSaveBudget(job.id, {
        payload: session,
        title: session.title,
        ...(documentVersion != null ? { expected_version: documentVersion } : {}),
      });
      handleSessionUpdated(saved.session);
      onSuccess?.(`"${saved.session.title}" salvo no banco de dados`, "Orçamento salvo");
      return saved.session;
    } catch (err) {
      if (err instanceof BudgetVersionConflictError) {
        onError?.(
          "Outro save ocorreu antes deste. Recarregue o orçamento e tente novamente.",
          "Conflito de versão"
        );
        if (err.currentVersion != null) setDocumentVersion(err.currentVersion);
      } else {
        onError?.(err, "Falha ao salvar");
      }
      throw err;
    } finally {
      setSaving(false);
    }
  }, [session, job?.id, documentVersion, handleSessionUpdated, onError, onSuccess]);

  const handleProjectChange = useCallback(
    async (values: ProjectFormValues) => {
      if (!session) return;
      setLoading(true);
      try {
        const updated = await api.pricingUpdateProject(session.session_id, values);
        setSession(updated);
      } catch (err) {
        onError?.(err, "Dados do projeto");
      } finally {
        setLoading(false);
      }
    },
    [session, onError]
  );

  const handleCommercialChange = useCallback(
    async (values: CommercialFormValues) => {
      if (!session) return;
      setLoading(true);
      try {
        const updated = await api.pricingUpdateProject(session.session_id, values);
        setSession(updated);
      } catch (err) {
        onError?.(err, "Dados comerciais");
      } finally {
        setLoading(false);
      }
    },
    [session, onError]
  );

  const handleObraTypeChange = useCallback(
    async (type: string) => {
      if (!session) return;
      setObraType(type);
      setLoading(true);
      try {
        const updated = await api.pricingUpdateProject(session.session_id, { obra_type: type });
        setSession(updated);
      } catch (err) {
        onError?.(err, "Tipo de obra");
      } finally {
        setLoading(false);
      }
    },
    [session, onError]
  );

  const handlePriceBasesChange = useCallback(
    async (next: BudgetPriceBaseSelection[]) => {
      if (!session) return;
      setLoading(true);
      try {
        const updated = await api.pricingUpdateProject(session.session_id, { price_bases: next });
        setSession(updated);
      } catch (err) {
        onError?.(err, "Bases de preço");
      } finally {
        setLoading(false);
      }
    },
    [session, onError]
  );

  const handleSaveEtapa = useCallback(async () => {
    await persistBudget();
  }, [persistBudget]);

  const handleExportPdf = useCallback(
    async (docKey: string, label: string) => {
      if (!session) return;
      setExportingDoc(`pdf:${docKey}`);
      setLoading(true);
      try {
        await downloadApiFile(
          `/pricing/budget/${session.session_id}/export/pdf/${docKey}`,
          `${docKey.toUpperCase()}_${session.session_id.slice(0, 8)}.pdf`
        );
      } catch (err) {
        onError?.(err, `Falha ao gerar PDF ${label}`);
      } finally {
        setExportingDoc(null);
        setLoading(false);
      }
    },
    [session, onError]
  );

  const handleExportExcel = useCallback(
    async (docKey: string, label: string) => {
      if (!session) return;
      setExportingDoc(`xlsx:${docKey}`);
      setLoading(true);
      try {
        await downloadApiFile(
          `/pricing/budget/${session.session_id}/export/xlsx/${docKey}`,
          `${docKey.toUpperCase()}_${session.session_id.slice(0, 8)}.xlsx`
        );
      } catch (err) {
        onError?.(err, `Falha ao gerar Excel ${label}`);
      } finally {
        setExportingDoc(null);
        setLoading(false);
      }
    },
    [session, onError]
  );

  const handleExportXlsm = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    try {
      await downloadApiFile(
        `/pricing/budget/${session.session_id}/export/xlsm?sync=true`,
        `PPD_${(session.project?.projeto || session.title || "Orcamento").replace(/\s+/g, "_").slice(0, 40)}_${session.session_id.slice(0, 8)}.xlsm`
      );
    } catch (err) {
      onError?.(err, "Falha ao exportar PPD oficial (.xlsm)");
    } finally {
      setLoading(false);
    }
  }, [session, onError]);

  const isFullHeightView = useMemo(
    () => !!session && (activeTab === "cronograma" || activeTab === "especificacao"),
    [session, activeTab]
  );

  const visibleTabs = budgetTabsEnabled
    ? TABS
    : TABS.filter((t) => t.id === "lancar_precos" || t.id === "historico");

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {restoring && !job && (
        <div className="flex justify-center py-8">
          <LoadingSpinner label="Restaurando orçamento…" size="lg" />
        </div>
      )}

      <BudgetToolbar
        title={
          job || session
            ? (session?.title ?? job?.obra ?? job?.title ?? "Orçamento importado")
            : null
        }
        titleMeta={
          activeDbId
            ? `ID ${activeDbId.slice(0, 8)}…${documentVersion != null ? ` · v${documentVersion}` : ""}`
            : null
        }
        hasSession={!!session}
        loading={loading || saving}
        savedVersion={documentVersion}
        autoSaveHint={
          exportingDoc?.startsWith("xlsx:")
            ? "Gerando Excel… (orçamento analítico pode levar alguns segundos)"
            : exportingDoc?.startsWith("pdf:")
              ? "Gerando PDF…"
              : null
        }
        onNew={handleNewOrcamento}
        onSave={session && job?.id ? () => void persistBudget() : undefined}
        onExportExcel={session ? (key, label) => void handleExportExcel(key, label) : undefined}
        onExportPdf={session ? (key, label) => void handleExportPdf(key, label) : undefined}
        onExportXlsm={session ? () => void handleExportXlsm() : undefined}
      />

      <TabBar tabs={visibleTabs} active={activeTab} onChange={handleTabChange} />

      <div
        className={cn(
          "min-h-0 flex-1",
          isFullHeightView ? "flex flex-col overflow-hidden" : "overflow-y-auto"
        )}
      >
        <div className={cn(activeTab !== "lancar_precos" && "hidden", "relative")}>
          {loading && activeTab === "lancar_precos" && (
            <div className="absolute inset-0 z-10 flex items-start justify-center rounded-xl bg-slate-950/60 pt-24 backdrop-blur-sm">
              <LoadingSpinner label="Carregando orçamento…" size="lg" />
            </div>
          )}
          <BudgetLancarPrecosPanel
            key={panelResetToken}
            onError={onError}
            onSuccess={notifySuccess}
            onImported={handleImported}
            onSessionUpdated={handleSessionUpdated}
            onJobUpdated={handleJobUpdated}
            onBudgetGenerated={handleBudgetGenerated}
            reloadJobId={reloadJobId}
            onReloadJobComplete={handleReloadJobComplete}
            workspaceJob={job}
            workspaceSession={session}
            panelSyncToken={panelSyncToken}
          />
        </div>

        {activeTab === "historico" && (
          <BudgetLancarPrecosHistoricoTab
            activeJobId={job?.id}
            refreshToken={historicoRefresh}
            onOpen={handleOpenHistoricoJob}
            onOpenBudgetModule={handleOpenBudgetModule}
            onReprocess={handleReprocessHistoricoJob}
            onDelete={handleDeleteHistoricoJob}
            onError={onError}
          />
        )}

        {activeTab !== "lancar_precos" && activeTab !== "historico" && !session && (
          <p className="py-8 text-center text-sm text-slate-500">
            Importe um orçamento para acessar esta aba.
          </p>
        )}

        {session && activeTab === "analitico" && (
          <div>
            <BudgetAnaliticoTab session={session} />
          </div>
        )}

        {session && activeTab === "curva_abc" && (
          <div>
            <BudgetCurvaAbcTab session={session} />
          </div>
        )}

        {session && activeTab === "curva_s" && (
          <div>
            <BudgetCurvaSTab session={session} />
          </div>
        )}

        {session && activeTab === "histograma" && (
          <div>
            <BudgetHistogramaTab session={session} />
          </div>
        )}

        {session &&
          activeTab !== "lancar_precos" &&
          activeTab !== "historico" &&
          activeTab !== "analitico" &&
          activeTab !== "curva_abc" &&
          activeTab !== "curva_s" &&
          activeTab !== "histograma" && (
            <div className={cn("relative", isFullHeightView ? "flex min-h-0 flex-1 flex-col gap-2" : "space-y-4")}>
              {loading && (
                <div className="absolute inset-0 z-10 flex items-start justify-center rounded-xl bg-slate-950/60 pt-24 backdrop-blur-sm">
                  <LoadingSpinner label="Processando…" size="lg" />
                </div>
              )}

              {activeTab === "dados" && (
                <BudgetDadosTab
                  sessionId={session.session_id}
                  project={session.project}
                  grandTotal={session.grand_total ?? 0}
                  bdiTypes={bdiTypes}
                  priceBases={session.project?.price_bases ?? []}
                  savedItems={savedItems}
                  disabled={loading}
                  sinapiImported={sinapiImported}
                  onProjectChange={handleProjectChange}
                  onCommercialChange={handleCommercialChange}
                  onObraTypeChange={handleObraTypeChange}
                  onPriceBasesChange={handlePriceBasesChange}
                  onSessionUpdate={setSession}
                  onError={onError}
                />
              )}

              {activeTab === "etapas" && (
                <BudgetEtapasPanel
                  session={session}
                  loading={loading}
                  onUpdate={setSession}
                  onError={onError}
                  onSave={handleSaveEtapa}
                />
              )}

              {activeTab === "ppd" && (
                <BudgetSpreadsheet session={session} onUpdate={setSession} onCellEdit={handleCellEdit} />
              )}

              {activeTab === "memoria" && (
                <BudgetMemoryPanel
                  session={session}
                  loading={loading}
                  onUpdate={setSession}
                  onCellEdit={handleCellEdit}
                />
              )}

              {activeTab === "cronograma" && (
                <BudgetSchedulePanel
                  session={session}
                  loading={loading}
                  onUpdate={setSession}
                  onError={onError}
                />
              )}

              {activeTab === "especificacao" && (
                <BudgetTechSpecPanel
                  session={session}
                  loading={loading}
                  onUpdate={setSession}
                  onError={onError}
                />
              )}
            </div>
          )}
      </div>
    </div>
  );
}
