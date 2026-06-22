"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import ActionDialog from "@/components/ActionDialog";
import BudgetEtapasPanel from "@/components/BudgetEtapasPanel";
import BudgetMemoryPanel from "@/components/BudgetMemoryPanel";
import BudgetPriceBasesPanel from "@/components/BudgetPriceBasesPanel";
import BudgetProjectForm, { type ProjectFormValues } from "@/components/BudgetProjectForm";
import BudgetSchedulePanel from "@/components/BudgetSchedulePanel";
import BudgetTechSpecPanel from "@/components/BudgetTechSpecPanel";
import BudgetSavedPanel from "@/components/BudgetSavedPanel";
import BudgetTracePanel from "@/components/BudgetTracePanel";
import BudgetSpreadsheet from "@/components/BudgetSpreadsheet";
import BudgetToolbar from "@/components/BudgetToolbar";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import { useActivity } from "@/context/ActivityContext";
import { api, BUDGET_SESSION_RESTORED, formatApiError, syncBudgetSessionSnapshot } from "@/services/api";
import type {
  BdiObraType,
  BudgetPriceBaseSelection,
  BudgetSessionResponse,
  BudgetSummary,
} from "@/types/api";
import { cn } from "@/lib/utils";

type TabId = "etapas" | "planilha" | "memoria" | "cronograma" | "especificacao";

type DialogState = {
  open: boolean;
  title: string;
  message: string;
  variant: "success" | "error" | "confirm" | "info";
  onConfirm?: () => void;
};

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
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState<BudgetSessionResponse | null>(null);
  const [savedItems, setSavedItems] = useState<BudgetSummary[]>([]);
  const [activeDbId, setActiveDbId] = useState<string | null>(null);
  const [bdiTypes, setBdiTypes] = useState<BdiObraType[]>([]);
  const [sinapiImported, setSinapiImported] = useState(false);
  const [obraType, setObraType] = useState("RF");
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("etapas");
  const [dialog, setDialog] = useState<DialogState>({
    open: false,
    title: "",
    message: "",
    variant: "info",
  });
  const [projectName, setProjectName] = useState<string | null>(null);
  const projectDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { pushActivity } = useActivity();

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
            base_preco: values.base_preco,
          });
          setSession(updated);
        } catch {
          /* debounced save — ignore transient errors */
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
      setActiveTab("etapas");
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
      let result = await api.pricingImportModelTemplate(
        file,
        session?.session_id
      );
      setSession(result);
      if (result.project?.obra_type) setObraType(result.project.obra_type);
      setActiveTab("etapas");
    } catch (err) {
      if (session && formatApiError(err instanceof Error ? err.message : String(err)).includes("Sessão não encontrada")) {
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
        router.replace(`/budget?project=${loaded.project_id}`);
      }
      setActiveTab("etapas");
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

  const isFullHeightTab =
    !!session && (activeTab === "cronograma" || activeTab === "especificacao");

  return (
    <>
      <ShellHeader className={cn("px-6", isFullHeightTab && "shrink-0")} showModelsStatus>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Orçamento de Obra</h1>
          {!isFullHeightTab && (
            <p className="text-sm text-slate-500">
              Montagem semi-autônoma · etapas manuais · composição via base de preços
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
          isFullHeightTab ? "flex min-h-0 flex-col overflow-hidden px-4 py-3" : "overflow-y-auto px-6 py-6"
        )}
      >
        <div
          className={cn(
            isFullHeightTab
              ? "flex min-h-0 flex-1 flex-col gap-2"
              : "mx-auto grid max-w-6xl gap-4 lg:grid-cols-[1fr_260px]"
          )}
        >
          <div className={cn(isFullHeightTab ? "flex min-h-0 flex-1 flex-col gap-2" : "space-y-4")}>
            <BudgetToolbar
              hasSession={!!session}
              loading={loading}
              onNew={handleNew}
              onImportTemplate={handleImportTemplate}
              onSave={session ? handleSave : undefined}
              onRenumber={session ? handleRenumberItemization : undefined}
              onExport={
                session
                  ? () => window.open(api.pricingExportUrl(session.session_id), "_blank")
                  : undefined
              }
            />

            {!sinapiImported && (
              <div className="rounded-xl bg-amber-500/10 px-4 py-3 text-sm text-amber-200 ring-1 ring-amber-500/30">
                Importe ao menos um período SINAPI em{" "}
                <a href="/settings/price-bases" className="text-cyan-300 underline">
                  Configurações → Bases de preços
                </a>{" "}
                e selecione base, UF e versão abaixo antes de compor serviços.
              </div>
            )}

            {error && (
              <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
                {error}
              </div>
            )}

            {loading && !session && (
              <div className="flex justify-center py-12">
                <LoadingSpinner label="Processando…" size="lg" />
              </div>
            )}

            {!session && !loading && (
              <div className="rounded-xl bg-slate-800/20 py-12 text-center ring-1 ring-slate-700/40">
                <h2 className="text-lg font-semibold text-white">Novo orçamento</h2>
                <p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">
                  Crie um orçamento vazio, preencha os dados da obra e adicione etapas.
                  Importe um template PPD para carregar a estrutura WBS de modelos existentes.
                </p>
              </div>
            )}

            {session && (
              <div className={cn("relative", isFullHeightTab ? "flex min-h-0 flex-1 flex-col gap-2" : "space-y-4")}>
                {loading && (
                  <div className="absolute inset-0 z-10 flex items-start justify-center rounded-xl bg-slate-950/60 pt-24 backdrop-blur-sm">
                    <LoadingSpinner label="Processando…" size="lg" />
                  </div>
                )}

                {!isFullHeightTab && (
                  <>
                    <BudgetProjectForm
                      project={session.project}
                      bdiTypes={bdiTypes}
                      disabled={loading}
                      onChange={handleProjectChange}
                      onObraTypeChange={handleObraTypeChange}
                    />
                    <BudgetPriceBasesPanel
                      value={session.project?.price_bases ?? []}
                      disabled={loading}
                      onChange={handlePriceBasesChange}
                    />
                  </>
                )}

                <div className="flex shrink-0 gap-1 border-b border-slate-700/60">
                  {(["etapas", "planilha", "memoria", "cronograma", "especificacao"] as TabId[]).map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => setActiveTab(tab)}
                      className={cn(
                        "px-4 py-2 text-sm font-medium transition-colors",
                        activeTab === tab
                          ? "border-b-2 border-cyan-400 text-cyan-300"
                          : "text-slate-500 hover:text-slate-300"
                      )}
                    >
                      {tab === "etapas"
                        ? "Etapas e composições"
                        : tab === "planilha"
                          ? "Planilha PPD"
                          : tab === "memoria"
                            ? "Memória de cálculo"
                            : tab === "cronograma"
                              ? "Cronograma"
                              : "Especificação técnica"}
                    </button>
                  ))}
                </div>

                {activeTab === "etapas" ? (
                  <BudgetEtapasPanel
                    session={session}
                    loading={loading}
                    onUpdate={setSession}
                    onError={showActionError}
                    onSave={handleSaveEtapa}
                  />
                ) : activeTab === "planilha" ? (
                  <BudgetSpreadsheet
                    session={session}
                    onUpdate={setSession}
                    onCellEdit={handleCellEdit}
                  />
                ) : activeTab === "memoria" ? (
                  <BudgetMemoryPanel
                    session={session}
                    loading={loading}
                    onUpdate={setSession}
                    onCellEdit={handleCellEdit}
                  />
                ) : activeTab === "cronograma" ? (
                  <BudgetSchedulePanel
                    session={session}
                    loading={loading}
                    onUpdate={setSession}
                    onError={showActionError}
                  />
                ) : (
                  <BudgetTechSpecPanel
                    session={session}
                    loading={loading}
                    onUpdate={setSession}
                    onError={showActionError}
                  />
                )}
              </div>
            )}
          </div>

          {!isFullHeightTab && (
            <>
              <BudgetTracePanel
                projectId={linkedProjectId}
                savedItems={savedItems}
                className="mt-4"
              />
              <BudgetSavedPanel
                items={savedItems}
                activeId={activeDbId}
                projectFilterLabel={projectId ? projectName ?? "Projeto selecionado" : null}
                onOpen={handleOpenSaved}
                onDelete={handleDeleteSaved}
                onNew={handleNew}
                onClearProjectFilter={projectId ? () => router.push("/budget") : undefined}
              />
            </>
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
