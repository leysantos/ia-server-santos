"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import ActionDialog from "@/components/ActionDialog";
import BudgetAnaliticoTab from "@/components/BudgetAnaliticoTab";
import BudgetAuditTab from "@/components/BudgetAuditTab";
import BudgetCpuSearchTab from "@/components/BudgetCpuSearchTab";
import BudgetCurvaAbcTab from "@/components/BudgetCurvaAbcTab";
import BudgetCurvaSTab from "@/components/BudgetCurvaSTab";
import BudgetHistogramaTab from "@/components/BudgetHistogramaTab";
import BudgetDadosTab from "@/components/BudgetDadosTab";
import BudgetEtapasPanel from "@/components/BudgetEtapasPanel";
import BudgetHistoricoTab from "@/components/BudgetHistoricoTab";
import BudgetMemoryPanel from "@/components/BudgetMemoryPanel";
import BudgetPipelinePanel, { type PipelineLogEntry, type PricingResolveEvent } from "@/components/BudgetPipelinePanel";
import BudgetRevisionPanel from "@/components/BudgetRevisionPanel";
import BudgetSchedulePanel from "@/components/BudgetSchedulePanel";
import BudgetTechSpecPanel from "@/components/BudgetTechSpecPanel";
import BudgetSpreadsheet from "@/components/BudgetSpreadsheet";
import BudgetToolbar from "@/components/BudgetToolbar";
import BudgetNewModal from "@/components/BudgetNewModal";
import type { ProjectFormValues } from "@/components/BudgetProjectForm";
import type { CommercialFormValues } from "@/components/BudgetCommercialPanel";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import { useActivity } from "@/context/ActivityContext";
import { api, BUDGET_SESSION_RESTORED, BudgetVersionConflictError, budgetGenerateStream, clearBudgetSessionSnapshot, downloadApiFile, formatApiError, restoreBudgetSessionFromStorage, syncBudgetSessionSnapshot } from "@/services/api";
import type {
  BdiObraType,
  BudgetPriceBaseSelection,
  BudgetSessionResponse,
  BudgetSkeleton,
  BudgetSummary,
} from "@/types/api";
import { cn, generateId } from "@/lib/utils";
import { useBudgetAutoSave } from "@/hooks/useBudgetAutoSave";
import { prefetchBudgetServiceCompositions } from "@/hooks/useBudgetServiceCompositions";

type BudgetTabId =
  | "dados"
  | "etapas"
  | "ppd"
  | "analitico"
  | "busca_cpu"
  | "memoria"
  | "cronograma"
  | "curva_abc"
  | "curva_s"
  | "histograma"
  | "especificacao"
  | "historico"
  | "auditoria";

type DialogState = {
  open: boolean;
  title: string;
  message: string;
  variant: "success" | "error" | "confirm" | "info";
  onConfirm?: () => void;
};

const BUDGET_TABS: { id: BudgetTabId; label: string }[] = [
  { id: "dados", label: "Dados do orçamento" },
  { id: "etapas", label: "Etapas e composições" },
  { id: "ppd", label: "Orç. Sintético" },
  { id: "analitico", label: "Orç. Analítico" },
  { id: "busca_cpu", label: "Busca CPU" },
  { id: "memoria", label: "Memória de cálculo" },
  { id: "cronograma", label: "Cronograma" },
  { id: "curva_abc", label: "Curva ABC" },
  { id: "curva_s", label: "Curva S" },
  { id: "histograma", label: "Histograma" },
  { id: "especificacao", label: "Especificação técnica" },
  { id: "auditoria", label: "Auditoria" },
  { id: "historico", label: "Histórico" },
];

const BUDGET_TAB_IDS = new Set<BudgetTabId>(BUDGET_TABS.map((t) => t.id));

const BUDGET_LAST_TAB_KEY = "iaserver.budget.lastTab";

function parseBudgetTab(value: string | null): BudgetTabId {
  if (value && BUDGET_TAB_IDS.has(value as BudgetTabId)) {
    return value as BudgetTabId;
  }
  if (typeof window !== "undefined") {
    const last = sessionStorage.getItem(BUDGET_LAST_TAB_KEY);
    if (last && BUDGET_TAB_IDS.has(last as BudgetTabId)) {
      return last as BudgetTabId;
    }
  }
  return "historico";
}

function BudgetTabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: BudgetTabId; label: string }[];
  active: BudgetTabId;
  onChange: (id: BudgetTabId) => void;
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
            data-testid={`budget-tab-${tab.id}`}
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

export default function BudgetPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center">
          <LoadingSpinner label="Carregando orçamento..." size="lg" />
        </div>
      }
    >
      <BudgetPageContent />
    </Suspense>
  );
}

function BudgetPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project");
  const tabFromUrl = searchParams.get("tab");
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState<BudgetSessionResponse | null>(null);
  const [savedItems, setSavedItems] = useState<BudgetSummary[]>([]);
  const [activeDbId, setActiveDbId] = useState<string | null>(null);
  const [documentVersion, setDocumentVersion] = useState<number | null>(null);
  const [bdiTypes, setBdiTypes] = useState<BdiObraType[]>([]);
  const [sinapiImported, setSinapiImported] = useState(false);
  const [obraType, setObraType] = useState("RF");
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTabState] = useState<BudgetTabId>(() => parseBudgetTab(tabFromUrl));
  const [restoringSession, setRestoringSession] = useState(true);
  const [dialog, setDialog] = useState<DialogState>({
    open: false,
    title: "",
    message: "",
    variant: "info",
  });
  const [projectName, setProjectName] = useState<string | null>(null);
  const projectDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialSessionRestoreDone = useRef(false);
  const { pushActivity } = useActivity();
  const [showNewModal, setShowNewModal] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [pipelineLogs, setPipelineLogs] = useState<PipelineLogEntry[]>([]);
  const [llmTokens, setLlmTokens] = useState("");
  const [generatePrompt, setGeneratePrompt] = useState("");
  const [useLlmGenerate, setUseLlmGenerate] = useState(true);
  const lastInputRef = useRef("");
  const actionParam = searchParams.get("action");

  const setActiveTab = useCallback(
    (tab: BudgetTabId) => {
      setActiveTabState(tab);
      if (typeof window !== "undefined") {
        sessionStorage.setItem(BUDGET_LAST_TAB_KEY, tab);
      }
      const params = new URLSearchParams(searchParams.toString());
      if (tab === "historico") {
        params.delete("tab");
      } else {
        params.set("tab", tab);
      }
      const qs = params.toString();
      router.replace(qs ? `/budget?${qs}` : "/budget", { scroll: false });
    },
    [router, searchParams]
  );

  useEffect(() => {
    setActiveTabState(parseBudgetTab(searchParams.get("tab")));
  }, [searchParams]);

  useEffect(() => {
    if (!initialSessionRestoreDone.current || !session) return;
    syncBudgetSessionSnapshot(session);
  }, [session]);

  /** Pré-carrega CPUs do histograma em background quando há cronograma. */
  useEffect(() => {
    if (!session?.session_id || !session.schedule?.project_start) return;
    const timer = window.setTimeout(() => {
      void prefetchBudgetServiceCompositions(session);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [session]);

  useEffect(() => {
    let cancelled = false;
    void restoreBudgetSessionFromStorage()
      .then((restored) => {
        if (!cancelled && restored) {
          setSession(restored);
          if (restored.db_id) setActiveDbId(restored.db_id);
          if (restored.document_version != null) setDocumentVersion(restored.document_version);
        }
      })
      .finally(() => {
        if (!cancelled) {
          initialSessionRestoreDone.current = true;
          setRestoringSession(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshSaved = useCallback(
    () =>
      api
        .pricingListSaved(projectId ?? undefined)
        .then((r) => setSavedItems(r.items))
        .catch(() => {}),
    [projectId]
  );

  const linkedProjectId = useMemo(
    () => projectId ?? session?.project_id ?? null,
    [projectId, session?.project_id]
  );

  const refreshSinapiStatus = useCallback(async () => {
    try {
      const res = await api.pricingSyncBankReferences();
      setSinapiImported((res.references ?? []).length > 0);
    } catch {
      setSinapiImported(false);
    }
  }, []);

  useEffect(() => {
    api.pricingBdiTypes().then((r) => {
      setBdiTypes(r.types);
      setObraType(r.default);
    }).catch(() => {});
    refreshSaved();
    refreshSinapiStatus();
  }, [refreshSinapiStatus, refreshSaved]);

  useEffect(() => {
    if (!projectId) {
      setProjectName(null);
      return;
    }
    api
      .project(projectId)
      .then((project) => setProjectName(project.name))
      .catch(() => setProjectName(null));
  }, [projectId]);

  useEffect(() => {
    if (!session?.session_id || restoringSession) return;
    const sid = session.session_id;
    void api.pricingAcquireBudgetLock(sid).catch(() => {});
    const renewTimer = window.setInterval(() => {
      void api.pricingRenewBudgetLock(sid).catch(() => {});
    }, 120_000);
    return () => {
      window.clearInterval(renewTimer);
      void api.pricingReleaseBudgetLock(sid).catch(() => {});
    };
  }, [session?.session_id, restoringSession]);

  useEffect(() => {
    if (restoringSession) return;
    if (actionParam === "new") {
      setShowNewModal(true);
      const params = new URLSearchParams(searchParams.toString());
      params.delete("action");
      const qs = params.toString();
      router.replace(qs ? `/budget?${qs}` : "/budget", { scroll: false });
    }
  }, [actionParam, restoringSession, router, searchParams]);

  const applyDefaultPriceBases = useCallback(async (result: BudgetSessionResponse) => {
    try {
      const refs = await api.pricingSyncBankReferences();
      const first = refs.references?.[0];
      if (first?.reference) {
        return api.pricingUpdateProject(result.session_id, {
          price_bases: [
            {
              source: "sinapi",
              label: "SINAPI",
              enabled: true,
              uf: "SP",
              reference: first.reference,
            },
          ],
        });
      }
    } catch {
      /* aplica depois na UI */
    }
    return result;
  }, []);

  const finalizeNewSession = useCallback(
    async (result: BudgetSessionResponse, tab: BudgetTabId = "dados") => {
      const nextSession = await applyDefaultPriceBases(result);
      setSession(nextSession);
      setActiveDbId(null);
      setDocumentVersion(null);
      if (nextSession.project?.obra_type) setObraType(nextSession.project.obra_type);
      setActiveTab(tab);
      setShowNewModal(false);
    },
    [applyDefaultPriceBases, setActiveTab]
  );


  useEffect(() => {
    const onRestored = (event: Event) => {
      const restored = (event as CustomEvent<BudgetSessionResponse>).detail;
      if (restored) setSession(restored);
    };
    window.addEventListener(BUDGET_SESSION_RESTORED, onRestored);
    return () => window.removeEventListener(BUDGET_SESSION_RESTORED, onRestored);
  }, []);

  const showActionError = useCallback((err: unknown, title = "Erro na operação") => {
    setDialog({
      open: true,
      title,
      message: formatApiError(err instanceof Error ? err.message : String(err)),
      variant: "error",
    });
  }, []);

  const priceBasesDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const commercialDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const persistProject = useCallback(
    (values: ProjectFormValues) => {
      if (!session) return;
      if (projectDebounce.current) clearTimeout(projectDebounce.current);
      projectDebounce.current = setTimeout(async () => {
        try {
          const updated = await api.pricingUpdateProject(session.session_id, {
            projeto: values.projeto,
            local: values.local,
            empresa: values.empresa,
            responsavel_tecnico: values.responsavel_tecnico,
            orcamento: values.orcamento,
            base_preco: values.base_preco,
          });
          setSession(updated);
        } catch {
          /* debounced save */
        }
      }, 600);
    },
    [session]
  );

  const handlePriceBasesChange = (next: BudgetPriceBaseSelection[]) => {
    if (!session) return;
    setSession({
      ...session,
      project: {
        ...session.project,
        price_bases: next,
      },
    });
    if (priceBasesDebounce.current) clearTimeout(priceBasesDebounce.current);
    priceBasesDebounce.current = setTimeout(async () => {
      try {
        const updated = await api.pricingUpdateProject(session.session_id, {
          price_bases: next,
        });
        setSession(updated);
      } catch (err) {
        showActionError(err, "Falha ao aplicar bases de preços");
      }
    }, 500);
  };

  const handleProjectChange = (values: ProjectFormValues) => {
    if (!session) return;
    setSession({
      ...session,
      title: values.projeto || session.title,
      project: {
        ...session.project,
        projeto: values.projeto,
        local: values.local,
        empresa: values.empresa,
        responsavel_tecnico: values.responsavel_tecnico,
        orcamento: values.orcamento,
        base_preco: values.base_preco,
        obra_type: values.obra_type,
      },
    });
    persistProject(values);
  };

  const persistCommercial = useCallback(
    (values: CommercialFormValues) => {
      if (!session) return;
      if (commercialDebounce.current) clearTimeout(commercialDebounce.current);
      commercialDebounce.current = setTimeout(async () => {
        try {
          const updated = await api.pricingUpdateProject(session.session_id, {
            commercial_margin_pct: values.commercial_margin_pct,
            commercial_client: values.commercial_client,
          });
          setSession(updated);
        } catch {
          /* debounced save */
        }
      }, 600);
    },
    [session]
  );

  const handleCommercialChange = (values: CommercialFormValues) => {
    if (!session) return;
    setSession({
      ...session,
      project: {
        ...session.project,
        commercial_margin_pct: values.commercial_margin_pct,
        commercial_client: values.commercial_client,
      },
    });
    persistCommercial(values);
  };

  const handleObraTypeChange = async (newType: string) => {
    setObraType(newType);
    if (!session) return;
    setLoading(true);
    try {
      const updated = await api.pricingUpdateBdi(session.session_id, newType);
      setSession(updated);
    } catch (err) {
      setError(formatApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  };

  const handleExportPdf = async (docKey: string, label: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await downloadApiFile(
        `/pricing/budget/${session.session_id}/export/pdf/${docKey}`,
        `${docKey.toUpperCase()}_${session.session_id.slice(0, 8)}.pdf`
      );
    } catch (err) {
      showActionError(err, `Falha ao gerar PDF ${label}`);
    } finally {
      setLoading(false);
    }
  };

  const handleExportExcel = async (docKey: string, label: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await downloadApiFile(
        `/pricing/budget/${session.session_id}/export/xlsx/${docKey}`,
        `${docKey.toUpperCase()}_${session.session_id.slice(0, 8)}.xlsx`
      );
    } catch (err) {
      showActionError(err, `Falha ao gerar Excel ${label}`);
    } finally {
      setLoading(false);
    }
  };

  const handleExportXlsm = async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await downloadApiFile(
        `/pricing/budget/${session.session_id}/export/xlsm?sync=true`,
        `PPD_${(session.project?.projeto || session.title || "Orcamento").replace(/\s+/g, "_").slice(0, 40)}_${session.session_id.slice(0, 8)}.xlsm`
      );
    } catch (err) {
      showActionError(err, "Falha ao exportar PPD oficial (.xlsm)");
    } finally {
      setLoading(false);
    }
  };

  const handleExportCompliance = async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await downloadApiFile(
        `/pricing/budget/${session.session_id}/export/compliance-pack.json`,
        `compliance_${session.session_id.slice(0, 8)}.json`
      );
    } catch (err) {
      showActionError(err, "Falha ao baixar pacote compliance");
    } finally {
      setLoading(false);
    }
  };

  const handleNew = () => {
    setShowNewModal(true);
  };

  const pushPipelineLog = useCallback((entry: Omit<PipelineLogEntry, "id" | "timestamp">) => {
    setPipelineLogs((prev) => [...prev, { ...entry, id: generateId(), timestamp: Date.now() }]);
  }, []);

  const handleGenerate = async () => {
    const text = generatePrompt.trim();
    if (!text || streaming) return;

    lastInputRef.current = text;
    setStreaming(true);
    setError(null);
    setPipelineLogs([]);
    setLlmTokens("");

    pushActivity({
      source: "budget",
      message: "Pipeline IA — gerando orçamento…",
      status: "running",
      phase: "generate",
    });

    try {
      let finalSession: BudgetSessionResponse | null = null;

      for await (const event of budgetGenerateStream({
        text,
        use_llm: useLlmGenerate,
        source_priority: ["sinapi"],
        obra_type: obraType,
        existing_session_id: session?.session_id,
      })) {
        if (event.type === "status") {
          pushPipelineLog({
            type: "status",
            message: String(event.data.message ?? "Processando…"),
            step: String(event.data.step ?? event.data.phase ?? ""),
            llmModel: event.data.llm_model ? String(event.data.llm_model) : undefined,
          });
        }

        if (event.type === "token") {
          const token = String(event.data.token ?? "");
          if (token) setLlmTokens((prev) => prev + token);
        }

        if (event.type === "step") {
          const step = String(event.data.step ?? "");
          if (step === "wbs_planner" && event.data.intent) {
            const intent = event.data.intent as Record<string, unknown>;
            const etapas = intent.etapas as unknown[] | undefined;
            pushPipelineLog({
              type: "step",
              step,
              message: `scope=${String(intent.scope ?? "—")} · ${etapas?.length ?? 0} etapa(s)`,
              llmModel: intent.llm_model ? String(intent.llm_model) : undefined,
            });
            setLlmTokens("");
          } else if (step === "intent_parser" && event.data.intent) {
            const intent = event.data.intent as Record<string, unknown>;
            pushPipelineLog({
              type: "step",
              step,
              message: `scope=${String(intent.scope ?? "—")} · parser=${String(intent.parser ?? "—")}`,
              llmModel: intent.llm_model ? String(intent.llm_model) : undefined,
            });
            setLlmTokens("");
          } else if (step === "quantity_engine" && event.data.memory) {
            const mem = event.data.memory as Record<string, unknown>;
            pushPipelineLog({
              type: "step",
              step,
              message: `${String(mem.formula ?? "qty")} = ${String(mem.result ?? "—")} ${String(mem.unit ?? "")}`,
            });
          } else if (step === "pricing_engine") {
            const faiss = event.data.faiss_index as Record<string, unknown> | undefined;
            if (faiss) {
              pushPipelineLog({
                type: "step",
                step,
                message: "Índice FAISS de composições pronto",
                faissIndex: {
                  indexed: Number(faiss.indexed ?? faiss.count ?? 0),
                  label: faiss.label ? String(faiss.label) : undefined,
                  total_rows: faiss.total_rows ? Number(faiss.total_rows) : undefined,
                },
              });
            } else if (event.data.items_priced !== undefined) {
              pushPipelineLog({
                type: "step",
                step,
                message:
                  `${event.data.items_priced} itens precificados de ${event.data.total_rows} linhas` +
                  (event.data.unresolved ? ` · ${event.data.unresolved} sem match` : ""),
              });
            }
          } else if (event.data.message) {
            pushPipelineLog({
              type: "step",
              step,
              message: String(event.data.message),
            });
          }
        }

        if (event.type === "pricing_resolve") {
          pushPipelineLog({
            type: "pricing_resolve",
            step: "pricing_engine",
            message: "",
            pricing: event.data as unknown as PricingResolveEvent,
          });
        }

        if (event.type === "error") {
          const msg = String(event.data.message ?? "Erro no pipeline");
          pushPipelineLog({ type: "error", message: msg });
          setError(msg);
        }

        if (event.type === "done") {
          finalSession = event.data as unknown as BudgetSessionResponse;
          pushPipelineLog({
            type: "done",
            message: `Orçamento gerado — R$ ${Number(finalSession.grand_total).toLocaleString("pt-BR")}`,
          });
        }
      }

      if (finalSession) {
        const nextSession = await applyDefaultPriceBases(finalSession);
        setSession(nextSession);
        setActiveDbId(null);
        setDocumentVersion(null);
        if (nextSession.project?.obra_type) setObraType(nextSession.project.obra_type);
        setActiveTab("dados");
        setGeneratePrompt("");
        pushActivity({
          source: "budget",
          message: `Orçamento gerado: ${nextSession.title}`,
          status: "done",
          phase: "generate",
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro ao gerar orçamento";
      setError(msg);
      pushPipelineLog({ type: "error", message: msg });
      pushActivity({
        source: "budget",
        message: msg,
        status: "error",
        phase: "generate",
      });
    } finally {
      setStreaming(false);
      setLlmTokens("");
    }
  };

  const handleNewBlank = async () => {
    setLoading(true);
    setError(null);
    setActiveDbId(null);
    try {
      const result = await api.pricingNewTemplate(obraType);
      await finalizeNewSession(result, "dados");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar orçamento");
    } finally {
      setLoading(false);
    }
  };

  const handleImportPpd = async (file: File) => {
    setLoading(true);
    setError(null);
    setActiveDbId(null);
    setDocumentVersion(null);
    try {
      const result = await api.pricingImportPpd(file);
      await finalizeNewSession(result, "dados");
      pushActivity({
        source: "budget",
        message: `PPD importado: ${file.name}`,
        status: "done",
        phase: "import",
      });
    } catch (err) {
      showActionError(err, "Falha ao importar PPD");
    } finally {
      setLoading(false);
    }
  };

  const handleNewFromSkeleton = async (skeleton: BudgetSkeleton, projeto: string) => {
    setLoading(true);
    setError(null);
    setActiveDbId(null);
    try {
      const result = await api.pricingNewFromSkeleton(skeleton.id, {
        projeto: projeto || skeleton.name,
        obraType: skeleton.obra_type || obraType,
      });
      await finalizeNewSession(result, "etapas");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar orçamento");
    } finally {
      setLoading(false);
    }
  };


  const handleCellEdit = useCallback(
    async (rowId: string, field: string, value: number | string, code?: string) => {
      if (!session) throw new Error("Sem sessão");
      return api.pricingUpdateCell(session.session_id, { row_id: rowId, field, value, code });
    },
    [session]
  );

  const persistBudget = useCallback(
    async (opts?: { showDialog?: boolean; etapaName?: string; silent?: boolean }) => {
      if (!session) return;
      if (!opts?.silent) setLoading(true);
      try {
        const body = {
          title: session.title,
          input_text: "",
          payload: session,
          ...(linkedProjectId ? { project_id: linkedProjectId } : {}),
          ...(activeDbId && documentVersion != null
            ? { expected_version: documentVersion }
            : {}),
        };
        const saved = activeDbId
          ? await api.pricingUpdateSaved(activeDbId, body)
          : await api.pricingSaveBudget(body);
        setSession(saved);
        setActiveDbId(saved.db_id ?? activeDbId);
        if (saved.document_version != null) setDocumentVersion(saved.document_version);
        if (saved.project_id && saved.project_id !== projectId) {
          router.replace(`/budget?project=${saved.project_id}`);
        }
        await refreshSaved();
        pushActivity({
          source: "budget",
          message: `Orçamento salvo: ${saved.title}`,
          status: "done",
          phase: "persist",
          projectId: linkedProjectId ?? undefined,
        });
        if (opts?.showDialog !== false) {
          setDialog({
            open: true,
            title: opts?.etapaName ? "Etapa salva" : "Orçamento salvo",
            message: opts?.etapaName
              ? `"${opts.etapaName}" e demais alterações foram persistidas no banco.`
              : `"${saved.title}" persistido no banco de dados${
                  linkedProjectId && projectName ? ` · projeto ${projectName}` : ""
                }.`,
            variant: "success",
          });
        }
        return saved;
      } catch (err) {
        if (err instanceof BudgetVersionConflictError) {
          setDialog({
            open: true,
            title: "Conflito de versão",
            message:
              "Outro usuário ou aba salvou este orçamento antes. Recarregue o documento do histórico e reaplique suas alterações.",
            variant: "error",
          });
          if (err.currentVersion != null) setDocumentVersion(err.currentVersion);
        } else if (opts?.showDialog !== false) {
          setDialog({
            open: true,
            title: "Falha ao salvar",
            message: err instanceof Error ? err.message : "Erro desconhecido",
            variant: "error",
          });
        }
        throw err;
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [session, activeDbId, documentVersion, linkedProjectId, projectId, projectName, refreshSaved, router, pushActivity]
  );

  const { autoSaveHint } = useBudgetAutoSave({
    session,
    activeDbId,
    baselineFrozen: session?.baseline_frozen,
    loading,
    persistBudget,
  });

  const handleSave = () => persistBudget();

  const handleRenumberItemization = async () => {
    if (!session) return;
    setLoading(true);
    try {
      const updated = await api.pricingRenumberItemization(session.session_id);
      setSession(updated);
    } catch (err) {
      showActionError(err, "Erro ao organizar numeração");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEtapa = useCallback(
    async ({ etapaName }: { etapaCode: string; etapaName: string }) => {
      await persistBudget({ showDialog: false, etapaName });
    },
    [persistBudget]
  );

  const handleOpenSaved = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await api.pricingGetSaved(id);
      setSession(loaded);
      setActiveDbId(id);
      setDocumentVersion(loaded.document_version ?? null);
      if (loaded.project?.obra_type) setObraType(loaded.project.obra_type);
      if (loaded.project_id && loaded.project_id !== projectId) {
        const params = new URLSearchParams(searchParams.toString());
        params.set("project", loaded.project_id);
        const qs = params.toString();
        router.replace(qs ? `/budget?${qs}` : "/budget");
      }
      const urlTab = parseBudgetTab(searchParams.get("tab"));
      setActiveTab(urlTab !== "historico" ? urlTab : "etapas");
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao abrir",
        message: err instanceof Error ? err.message : "Falha ao carregar",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSaved = (id: string) => {
    const item = savedItems.find((s) => s.id === id);
    setDialog({
      open: true,
      title: "Excluir orçamento?",
      message: `Confirma exclusão de "${item?.title ?? id}"?`,
      variant: "confirm",
      onConfirm: async () => {
        try {
          await api.pricingDeleteSaved(id);
          if (activeDbId === id) {
            setActiveDbId(null);
            setDocumentVersion(null);
            setSession(null);
            clearBudgetSessionSnapshot();
          }
          await refreshSaved();
        } catch (err) {
          setDialog({
            open: true,
            title: "Falha ao excluir",
            message: err instanceof Error ? err.message : "Erro",
            variant: "error",
          });
        }
      },
    });
  };

  const isFullHeightView =
    !!session && (activeTab === "cronograma" || activeTab === "especificacao");

  const sessionPriceBases = session?.project?.price_bases ?? [];

  return (
    <>
      <ShellHeader className={cn("px-6", isFullHeightView && "shrink-0")} showModelsStatus>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Orçamento de Obra</h1>
          {!isFullHeightView && (
            <p className="text-sm text-slate-500">
              Dados da obra · etapas · sintético · analítico · curvas · histórico
            </p>
          )}
          {projectId && (
            <p className="mt-1 text-sm text-cyan-300">
              Vinculado ao projeto{" "}
              <Link href={`/projects/${projectId}`} className="underline hover:text-cyan-200">
                {projectName ?? projectId.slice(0, 8)}
              </Link>
            </p>
          )}
        </div>
      </ShellHeader>

      <div
        className={cn(
          "flex-1",
          isFullHeightView ? "flex min-h-0 flex-col overflow-hidden px-4 py-3" : "overflow-y-auto px-4 py-6 lg:px-8"
        )}
      >
        <div
          className={cn(
            "mx-auto w-full",
            isFullHeightView ? "flex min-h-0 flex-1 flex-col gap-2 max-w-[1600px]" : "max-w-[1600px] space-y-4"
          )}
        >
          <BudgetToolbar
            hasSession={!!session}
            loading={loading}
            savedVersion={activeDbId ? documentVersion : null}
            autoSaveHint={autoSaveHint}
            onNew={handleNew}
            onSave={session ? handleSave : undefined}
            onRenumber={session ? handleRenumberItemization : undefined}
            onExportExcel={session ? (key, label) => void handleExportExcel(key, label) : undefined}
            onExportPdf={session ? (key, label) => void handleExportPdf(key, label) : undefined}
            onExportXlsm={session ? () => void handleExportXlsm() : undefined}
            onExportCompliance={session ? () => void handleExportCompliance() : undefined}
          />

          {session && activeDbId && (
            <BudgetRevisionPanel
              budgetId={activeDbId}
              session={session}
              disabled={loading}
              onOpenRevision={(loaded) => {
                setSession(loaded);
                setActiveDbId(loaded.db_id ?? null);
                setDocumentVersion(loaded.document_version ?? null);
                setActiveTab("etapas");
              }}
              onSessionUpdate={setSession}
              onError={showActionError}
            />
          )}

          {session?.baseline_frozen && activeDbId && (
            <div className="rounded-xl bg-teal-500/10 px-4 py-2 text-xs text-teal-200 ring-1 ring-teal-500/30">
              Baseline congelada — este documento é somente leitura. Crie uma revisão (aditivo) para alterar valores.
            </div>
          )}

          {error && (
            <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
              {error}
            </div>
          )}

          {(loading || restoringSession) && !session && (
            <div className="flex justify-center py-12">
              <LoadingSpinner
                label={restoringSession ? "Restaurando orçamento…" : "Processando…"}
                size="lg"
              />
            </div>
          )}

          {!session && !loading && !restoringSession && activeTab !== "historico" && activeTab !== "busca_cpu" && (
            <div className="rounded-xl bg-slate-800/20 py-12 text-center ring-1 ring-slate-700/40">
              <h2 className="text-lg font-semibold text-white">Novo orçamento</h2>
              <p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">
                Crie um orçamento vazio ou abra um salvo na aba Histórico. Configure dados da obra e bases
                de preços em Dados do orçamento.
              </p>
              <button
                type="button"
                onClick={() => setActiveTab("historico")}
                className="mt-4 text-sm text-cyan-400 underline hover:text-cyan-300"
              >
                Ver orçamentos salvos
              </button>
            </div>
          )}

          <BudgetTabBar tabs={BUDGET_TABS} active={activeTab} onChange={setActiveTab} />

          {session && (
            <div className={cn(activeTab !== "auditoria" && "hidden")}>
              <BudgetAuditTab sessionId={session.session_id} />
            </div>
          )}

          {activeTab === "auditoria" && !session && !loading && !restoringSession && (
            <p className="text-center text-sm text-slate-500 py-8">
              Abra ou crie um orçamento para ver a trilha de auditoria.
            </p>
          )}

          {activeTab === "historico" && (
            <div className="space-y-4">
              <section className="rounded-xl bg-slate-900/40 p-4 ring-1 ring-violet-500/20">
                <h2 className="text-sm font-semibold text-violet-200">Gerar orçamento com IA</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Descreva a obra — o pipeline monta WBS, quantitativos e precificação SINAPI em tempo real.
                </p>
                <textarea
                  value={generatePrompt}
                  onChange={(e) => setGeneratePrompt(e.target.value)}
                  placeholder="Ex.: Passarela metálica 12 m sobre córrego, fundação em estaca, pintura anticorrosiva…"
                  rows={3}
                  disabled={streaming}
                  className="mt-3 w-full resize-y rounded-lg border border-white/10 bg-surface-card px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-violet-500/40 focus:outline-none focus:ring-1 focus:ring-violet-500/30 disabled:opacity-50"
                />
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
                    <input
                      type="checkbox"
                      checked={useLlmGenerate}
                      onChange={(e) => setUseLlmGenerate(e.target.checked)}
                      disabled={streaming}
                      className="rounded border-white/10 bg-surface-card text-violet-500 focus:ring-violet-500/50"
                    />
                    Usar LLM (WBS planner)
                  </label>
                  <button
                    type="button"
                    disabled={streaming || !generatePrompt.trim()}
                    onClick={() => void handleGenerate()}
                    className={cn(
                      "ml-auto rounded-lg bg-violet-600/25 px-4 py-2 text-sm text-violet-100 ring-1 ring-violet-500/40",
                      "hover:bg-violet-600/35 disabled:cursor-not-allowed disabled:opacity-40"
                    )}
                  >
                    {streaming ? "Gerando…" : "Gerar orçamento"}
                  </button>
                </div>
              </section>

              <BudgetPipelinePanel logs={pipelineLogs} streaming={streaming} llmTokens={llmTokens} />

              <BudgetHistoricoTab
                savedItems={savedItems}
                activeId={activeDbId}
                projectFilterLabel={projectId ? projectName ?? "Projeto selecionado" : null}
                onOpen={handleOpenSaved}
                onDelete={handleDeleteSaved}
                onNew={handleNew}
                onClearProjectFilter={projectId ? () => router.push("/budget") : undefined}
              />
            </div>
          )}

          {session && (
            <div className={cn(activeTab !== "analitico" && "hidden")}>
              <BudgetAnaliticoTab session={session} />
            </div>
          )}

          {session && (
            <div className={cn(activeTab !== "curva_abc" && "hidden")}>
              <BudgetCurvaAbcTab
                session={session}
                onExportPdf={handleExportPdf}
                onExportExcel={handleExportExcel}
                exportDisabled={loading}
              />
            </div>
          )}

          {session && (
            <div className={cn(activeTab !== "curva_s" && "hidden")}>
              <BudgetCurvaSTab
                session={session}
                onExportPdf={handleExportPdf}
                onExportExcel={handleExportExcel}
                exportDisabled={loading}
              />
            </div>
          )}

          {session && (
            <div className={cn(activeTab !== "histograma" && "hidden")}>
              <BudgetHistogramaTab
                session={session}
                onExportPdf={handleExportPdf}
                onExportExcel={handleExportExcel}
                exportDisabled={loading}
              />
            </div>
          )}

          {activeTab === "analitico" && !session && !loading && !restoringSession && (
            <p className="text-center text-sm text-slate-500 py-8">
              Abra ou crie um orçamento para ver o espelho analítico dos serviços lançados.
            </p>
          )}

          {activeTab === "curva_abc" && !session && !loading && !restoringSession && (
            <p className="text-center text-sm text-slate-500 py-8">
              Abra ou crie um orçamento para ver a curva ABC.
            </p>
          )}

          {activeTab === "curva_s" && !session && !loading && !restoringSession && (
            <p className="text-center text-sm text-slate-500 py-8">
              Abra ou crie um orçamento para ver a curva S.
            </p>
          )}

          {activeTab === "histograma" && !session && !loading && !restoringSession && (
            <p className="text-center text-sm text-slate-500 py-8">
              Abra ou crie um orçamento para ver o histograma de demanda mensal.
            </p>
          )}

          {activeTab === "busca_cpu" && (
            <BudgetCpuSearchTab
              priceBases={sessionPriceBases}
              session={session}
              onSessionUpdate={setSession}
              onPriceBasesChange={handlePriceBasesChange}
              onError={showActionError}
            />
          )}

          {session && activeTab !== "historico" && activeTab !== "analitico" && activeTab !== "busca_cpu" && activeTab !== "curva_abc" && activeTab !== "curva_s" && activeTab !== "histograma" && (
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
                  onComplianceDownload={() => void handleExportCompliance()}
                  onObraTypeChange={handleObraTypeChange}
                  onPriceBasesChange={handlePriceBasesChange}
                  onSessionUpdate={setSession}
                  onError={showActionError}
                />
              )}

              {activeTab === "etapas" && (
                <BudgetEtapasPanel
                  session={session}
                  loading={loading}
                  onUpdate={setSession}
                  onError={showActionError}
                  onSave={handleSaveEtapa}
                />
              )}

              {activeTab === "ppd" && (
                <BudgetSpreadsheet
                  session={session}
                  onUpdate={setSession}
                  onCellEdit={handleCellEdit}
                />
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
                  onError={showActionError}
                />
              )}

              {activeTab === "especificacao" && (
                <BudgetTechSpecPanel
                  session={session}
                  loading={loading}
                  onUpdate={setSession}
                  onError={showActionError}
                />
              )}
            </div>
          )}

          {!session && activeTab === "dados" && (
            <p className="text-center text-sm text-slate-500 py-8">
              Crie ou abra um orçamento para editar os dados da obra.
            </p>
          )}

          {!session && activeTab === "etapas" && (
            <p className="text-center text-sm text-slate-500 py-8">
              Crie ou abra um orçamento para compor etapas e serviços.
            </p>
          )}

          {!session && activeTab === "ppd" && (
            <p className="text-center text-sm text-slate-500 py-8">
              Crie ou abra um orçamento para ver a planilha PPD.
            </p>
          )}

          {!session && activeTab === "memoria" && (
            <p className="text-center text-sm text-slate-500 py-8">
              Crie ou abra um orçamento para editar a memória de cálculo.
            </p>
          )}

          {!session && activeTab === "cronograma" && (
            <p className="text-center text-sm text-slate-500 py-8">
              Crie ou abra um orçamento para montar o cronograma.
            </p>
          )}

          {!session && activeTab === "especificacao" && (
            <p className="text-center text-sm text-slate-500 py-8">
              Crie ou abra um orçamento para a especificação técnica.
            </p>
          )}
        </div>
      </div>

      <BudgetNewModal
        open={showNewModal}
        obraType={obraType}
        loading={loading}
        onClose={() => setShowNewModal(false)}
        onSelectBlank={() => void handleNewBlank()}
        onSelectSkeleton={(sk, projeto) => void handleNewFromSkeleton(sk, projeto)}
        onImportPpd={(file) => void handleImportPpd(file)}
      />

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        variant={dialog.variant}
        confirmLabel={dialog.variant === "confirm" ? "Excluir" : "OK"}
        onConfirm={dialog.onConfirm}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
      />
    </>
  );
}
