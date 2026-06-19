"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ActionDialog from "@/components/ActionDialog";
import BudgetEtapasPanel from "@/components/BudgetEtapasPanel";
import BudgetMemoryPanel from "@/components/BudgetMemoryPanel";
import BudgetProjectForm, { type ProjectFormValues } from "@/components/BudgetProjectForm";
import BudgetSavedPanel from "@/components/BudgetSavedPanel";
import BudgetSpreadsheet from "@/components/BudgetSpreadsheet";
import BudgetToolbar from "@/components/BudgetToolbar";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import { api, BUDGET_SESSION_RESTORED, formatApiError, syncBudgetSessionSnapshot } from "@/services/api";
import type {
  BdiObraType,
  BudgetSessionResponse,
  BudgetSummary,
  KnowledgeCatalogEntry,
  PriceBaseActiveStatus,
  PriceBaseInfo,
} from "@/types/api";
import { cn } from "@/lib/utils";

type TabId = "etapas" | "planilha" | "memoria";

type DialogState = {
  open: boolean;
  title: string;
  message: string;
  variant: "success" | "error" | "confirm" | "info";
  onConfirm?: () => void;
};

type PriceBaseOption = PriceBaseInfo & { documentId?: string };

export default function BudgetPage() {
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState<BudgetSessionResponse | null>(null);
  const [savedItems, setSavedItems] = useState<BudgetSummary[]>([]);
  const [activeDbId, setActiveDbId] = useState<string | null>(null);
  const [bdiTypes, setBdiTypes] = useState<BdiObraType[]>([]);
  const [legacyBases, setLegacyBases] = useState<PriceBaseInfo[]>([]);
  const [catalogBases, setCatalogBases] = useState<PriceBaseOption[]>([]);
  const [priceBaseStatus, setPriceBaseStatus] = useState<PriceBaseActiveStatus | null>(null);
  const [obraType, setObraType] = useState("RF");
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("etapas");
  const [dialog, setDialog] = useState<DialogState>({
    open: false,
    title: "",
    message: "",
    variant: "info",
  });
  const projectDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshSaved = () =>
    api.pricingListSaved().then((r) => setSavedItems(r.items)).catch(() => {});

  const refreshBases = useCallback(async () => {
    const [pricingRes, catalogRes] = await Promise.all([
      api.pricingListBases().catch(() => ({ bases: [] as PriceBaseInfo[], active: undefined })),
      api.knowledgeCatalog(100).catch(() => ({ items: [] as KnowledgeCatalogEntry[] })),
    ]);
    setLegacyBases(pricingRes.bases);
    setPriceBaseStatus(pricingRes.active ?? null);
    const fromCatalog: PriceBaseOption[] = (catalogRes.items || [])
      .filter(
        (item) =>
          (item.content_type === "sinapi" || item.content_type === "tcpo") &&
          (item.price_item_count ?? 0) > 0
      )
      .map((item) => ({
        id: item.id,
        name: item.name || item.filename,
        filename: item.filename,
        format: item.content_type || "sinapi",
        item_count: item.price_item_count ?? 0,
        created_at: item.catalog_ts || "",
        active: pricingRes.active?.base_id === item.id,
        documentId: item.id,
      }));
    setCatalogBases(fromCatalog);
  }, []);

  useEffect(() => {
    api.pricingBdiTypes().then((r) => {
      setBdiTypes(r.types);
      setObraType(r.default);
    }).catch(() => {});
    refreshSaved();
    refreshBases();
  }, [refreshBases]);

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

  const priceBases = useMemo(() => {
    const seen = new Set<string>();
    const merged: PriceBaseOption[] = [];
    for (const b of [...catalogBases, ...legacyBases]) {
      if (seen.has(b.id)) continue;
      seen.add(b.id);
      merged.push(b);
    }
    return merged;
  }, [catalogBases, legacyBases]);

  const activeBaseId =
    priceBases.find((b) => b.active)?.id ||
    priceBaseStatus?.base_id ||
    "";

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

  const handleBaseChange = async (baseId: string, isKnowledge: boolean) => {
    if (!baseId) return;
    setLoading(true);
    try {
      if (isKnowledge) {
        await api.knowledgeActivatePriceBase(baseId);
      } else {
        await api.pricingActivateBase(baseId);
      }
      await refreshBases();
      if (session) {
        const base = priceBases.find((b) => b.id === baseId);
        const updated = await api.pricingUpdateProject(session.session_id, {
          base_preco: base?.name || "",
        });
        setSession(updated);
      }
    } catch (err) {
      setDialog({
        open: true,
        title: "Falha ao trocar base",
        message: err instanceof Error ? err.message : "Erro",
        variant: "error",
      });
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
      setSession(result);
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
        const body = { title: session.title, input_text: "", payload: session };
        const saved = activeDbId
          ? await api.pricingUpdateSaved(activeDbId, body)
          : await api.pricingSaveBudget(body);
        setSession(saved);
        setActiveDbId(saved.db_id ?? activeDbId);
        await refreshSaved();
        if (opts?.showDialog !== false) {
          setDialog({
            open: true,
            title: opts?.etapaName ? "Etapa salva" : "Orçamento salvo",
            message: opts?.etapaName
              ? `"${opts.etapaName}" e demais alterações foram persistidas no banco.`
              : `"${saved.title}" persistido no banco de dados.`,
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
    [session, activeDbId]
  );

  const handleSave = () => persistBudget();

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

  return (
    <>
      <ShellHeader className="px-6" showModelsStatus>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Orçamento de Obra</h1>
          <p className="text-sm text-slate-500">
            Montagem semi-autônoma · etapas manuais · composição via base de preços
          </p>
        </div>
      </ShellHeader>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[1fr_260px]">
          <div className="space-y-4">
            <BudgetToolbar
              hasSession={!!session}
              loading={loading}
              onNew={handleNew}
              onImportTemplate={handleImportTemplate}
              onSave={session ? handleSave : undefined}
              onExport={
                session
                  ? () => window.open(api.pricingExportUrl(session.session_id), "_blank")
                  : undefined
              }
            />

            {!priceBaseStatus?.loaded && (
              <div className="rounded-xl bg-amber-500/10 px-4 py-3 text-sm text-amber-200 ring-1 ring-amber-500/30">
                Configure uma base de preços em{" "}
                <a href="/settings" className="text-cyan-300 underline">
                  Configurações → Biblioteca
                </a>{" "}
                antes de compor serviços.
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
              <div className="relative space-y-4">
                {loading && (
                  <div className="absolute inset-0 z-10 flex items-start justify-center rounded-xl bg-slate-950/60 pt-24 backdrop-blur-sm">
                    <LoadingSpinner label="Processando…" size="lg" />
                  </div>
                )}

                <BudgetProjectForm
                  project={session.project}
                  bdiTypes={bdiTypes}
                  priceBases={priceBases}
                  activeBaseId={activeBaseId}
                  disabled={loading}
                  onChange={handleProjectChange}
                  onObraTypeChange={handleObraTypeChange}
                  onBaseChange={handleBaseChange}
                />

                <div className="flex gap-1 border-b border-slate-700/60">
                  {(["etapas", "planilha", "memoria"] as TabId[]).map((tab) => (
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
                          : "Memória de cálculo"}
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
                ) : (
                  <BudgetMemoryPanel
                    session={session}
                    loading={loading}
                    onUpdate={setSession}
                    onCellEdit={handleCellEdit}
                  />
                )}
              </div>
            )}
          </div>

          <BudgetSavedPanel
            items={savedItems}
            activeId={activeDbId}
            onOpen={handleOpenSaved}
            onDelete={handleDeleteSaved}
            onNew={handleNew}
          />
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
