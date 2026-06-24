"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import ActionDialog from "@/components/ActionDialog";
import BudgetAnaliticoTab from "@/components/BudgetAnaliticoTab";
import BudgetCpuSearchTab from "@/components/BudgetCpuSearchTab";
import BudgetDadosTab from "@/components/BudgetDadosTab";
import BudgetEtapasPanel from "@/components/BudgetEtapasPanel";
import BudgetHistoricoTab from "@/components/BudgetHistoricoTab";
import BudgetMemoryPanel from "@/components/BudgetMemoryPanel";
import BudgetSchedulePanel from "@/components/BudgetSchedulePanel";
import BudgetTechSpecPanel from "@/components/BudgetTechSpecPanel";
import BudgetSpreadsheet from "@/components/BudgetSpreadsheet";
import BudgetToolbar from "@/components/BudgetToolbar";
import type { ProjectFormValues } from "@/components/BudgetProjectForm";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import { useActivity } from "@/context/ActivityContext";
import { api, BUDGET_SESSION_RESTORED, formatApiError, restoreBudgetSessionFromStorage, syncBudgetSessionSnapshot } from "@/services/api";
import type {
  BdiObraType,
  BudgetPriceBaseSelection,
  BudgetSessionResponse,
  BudgetSummary,
} from "@/types/api";
import { cn } from "@/lib/utils";

type BudgetTabId =
  | "dados"
  | "etapas"
  | "ppd"
  | "analitico"
  | "busca_cpu"
  | "memoria"
  | "cronograma"
  | "especificacao"
  | "historico";

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
  { id: "especificacao", label: "Especificação técnica" },
  { id: "historico", label: "Histórico" },
];

const BUDGET_TAB_IDS = new Set<BudgetTabId>(BUDGET_TABS.map((t) => t.id));

function parseBudgetTab(value: string | null): BudgetTabId {
  if (value && BUDGET_TAB_IDS.has(value as BudgetTabId)) {
    return value as BudgetTabId;
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
  const { pushActivity } = useActivity();

  const setActiveTab = useCallback(
    (tab: BudgetTabId) => {
      setActiveTabState(tab);
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
    let cancelled = false;
    void restoreBudgetSessionFromStorage()
      .then((restored) => {
        if (!cancelled && restored) {
          setSession(restored);
        }
      })
      .finally(() => {
        if (!cancelled) setRestoringSession(false);
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
    syncBudgetSessionSnapshot(session);
  }, [session]);

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

  const handleNew = async () => {
    setLoading(true);
    setError(null);
    setActiveDbId(null);
    try {
      const result = await api.pricingNewTemplate(obraType);
      let nextSession = result;
      try {
        const refs = await api.pricingSyncBankReferences();
        const first = refs.references?.[0];
        if (first?.reference) {
          nextSession = await api.pricingUpdateProject(result.session_id, {
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
      setSession(nextSession);
      setActiveTab("dados");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar orçamento");
    } finally {
      setLoading(false);
    }
  };

  const handleImportTemplate = async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      let result = await api.pricingImportModelTemplate(file, session?.session_id);
      setSession(result);
      if (result.project?.obra_type) setObraType(result.project.obra_type);
      setActiveTab("etapas");
    } catch (err) {
      if (
        session &&
        formatApiError(err instanceof Error ? err.message : String(err)).includes("Sessão não encontrada")
      ) {
        try {
          syncBudgetSessionSnapshot(session);
          const result = await api.pricingImportModelTemplate(file);
          setSession(result);
          if (result.project?.obra_type) setObraType(result.project.obra_type);
          setActiveTab("etapas");
          return;
        } catch (retryErr) {
          setError(formatApiError(retryErr instanceof Error ? retryErr.message : String(retryErr)));
          return;
        }
      }
      setError(formatApiError(err instanceof Error ? err.message : String(err)));
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
    async (opts?: { showDialog?: boolean; etapaName?: string }) => {
      if (!session) return;
      setLoading(true);
      try {
        const body = {
          title: session.title,
          input_text: "",
          payload: session,
          ...(linkedProjectId ? { project_id: linkedProjectId } : {}),
        };
        const saved = activeDbId
          ? await api.pricingUpdateSaved(activeDbId, body)
          : await api.pricingSaveBudget(body);
        setSession(saved);
        setActiveDbId(saved.db_id ?? activeDbId);
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
        if (opts?.showDialog !== false) {
          setDialog({
            open: true,
            title: "Falha ao salvar",
            message: err instanceof Error ? err.message : "Erro desconhecido",
            variant: "error",
          });
        }
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [session, activeDbId, linkedProjectId, projectId, projectName, refreshSaved, router, pushActivity]
  );

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
            setSession(null);
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
              Dados da obra · etapas · sintético · analítico · histórico
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
            onNew={handleNew}
            onImportTemplate={handleImportTemplate}
            onSave={session ? handleSave : undefined}
            onRenumber={session ? handleRenumberItemization : undefined}
            onExport={
              session ? () => window.open(api.pricingExportUrl(session.session_id), "_blank") : undefined
            }
          />

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

          {activeTab === "historico" && (
            <BudgetHistoricoTab
              savedItems={savedItems}
              activeId={activeDbId}
              projectId={linkedProjectId}
              projectFilterLabel={projectId ? projectName ?? "Projeto selecionado" : null}
              onOpen={handleOpenSaved}
              onDelete={handleDeleteSaved}
              onNew={handleNew}
              onClearProjectFilter={projectId ? () => router.push("/budget") : undefined}
            />
          )}

          {session && (
            <div className={cn(activeTab !== "analitico" && "hidden")}>
              <BudgetAnaliticoTab session={session} />
            </div>
          )}

          {activeTab === "analitico" && !session && !loading && !restoringSession && (
            <p className="text-center text-sm text-slate-500 py-8">
              Abra ou crie um orçamento para ver o espelho analítico dos serviços lançados.
            </p>
          )}

          {activeTab === "busca_cpu" && (
            <BudgetCpuSearchTab priceBases={sessionPriceBases} />
          )}

          {session && activeTab !== "historico" && activeTab !== "analitico" && activeTab !== "busca_cpu" && (
            <div className={cn("relative", isFullHeightView ? "flex min-h-0 flex-1 flex-col gap-2" : "space-y-4")}>
              {loading && (
                <div className="absolute inset-0 z-10 flex items-start justify-center rounded-xl bg-slate-950/60 pt-24 backdrop-blur-sm">
                  <LoadingSpinner label="Processando…" size="lg" />
                </div>
              )}

              {activeTab === "dados" && (
                <BudgetDadosTab
                  project={session.project}
                  bdiTypes={bdiTypes}
                  priceBases={session.project?.price_bases ?? []}
                  savedItems={savedItems}
                  disabled={loading}
                  sinapiImported={sinapiImported}
                  onProjectChange={handleProjectChange}
                  onObraTypeChange={handleObraTypeChange}
                  onPriceBasesChange={handlePriceBasesChange}
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
