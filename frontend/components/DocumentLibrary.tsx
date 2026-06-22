"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ActionDialog from "@/components/ActionDialog";
import KnowledgeCatalogStatsCards from "@/components/KnowledgeCatalogStatsCards";
import { cn, formatDate } from "@/lib/utils";
import { useKnowledgeWebImportOptional } from "@/context/KnowledgeWebImportContext";
import type {
  KnowledgeCatalogEntry,
  KnowledgeIngestResponse,
  KnowledgeOptionsResponse,
  KnowledgeStatsResponse,
  DocumentTypePreset,
  WebIngestProgress,
} from "@/types/api";

const ACCEPT = ".pdf,.csv,.xlsx,.xls,.xlsm,.json,.md,.txt,.docx,.xml";

function resolveDocPreset(
  docType: string,
  presets: DocumentTypePreset[]
): {
  contentType: string;
  discipline: string;
  priceBase: boolean;
  budgetModel: boolean;
} | null {
  if (docType === "auto") return null;
  const preset = presets.find((p) => p.id === docType);
  if (!preset) return null;
  return {
    contentType: preset.content_type,
    discipline: preset.discipline,
    priceBase: preset.register_price_base,
    budgetModel: preset.register_budget_model,
  };
}

function presetSelectOptions(presets: DocumentTypePreset[]) {
  return presets.map((p) => (
    <option key={p.id} value={p.id}>
      {p.label}
    </option>
  ));
}

interface DocumentLibraryProps {
  view?: "all" | "import" | "catalog";
  options: KnowledgeOptionsResponse;
  catalog: KnowledgeCatalogEntry[];
  stats?: KnowledgeStatsResponse | null;
  onIngest?: (formData: FormData) => Promise<KnowledgeIngestResponse>;
  onIngestWeb?: (
    body: {
      page_url: string;
      discipline?: string;
      content_type?: string;
      force?: boolean;
      max_files?: number;
    },
    onProgress?: (progress: WebIngestProgress) => void
  ) => Promise<{
    discovered: number;
    downloaded: number;
    ingested: number;
    skipped?: number;
    pages_fetched?: number;
    errors: { error?: string; stage?: string; url?: string }[];
  }>;
  onActivatePriceBase?: (documentId: string) => Promise<void>;
  onIndexBudgetModel?: (documentId: string) => Promise<{
    service_count: number;
    reason?: string;
  }>;
  onUpdateDocument?: (
    documentId: string,
    payload: { name?: string; description?: string; content_type?: string; discipline?: string }
  ) => Promise<void>;
  onDeleteDocument?: (documentId: string) => Promise<void>;
  onRefresh?: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentLibrary({
  view = "all",
  options,
  catalog,
  stats = null,
  onIngest,
  onActivatePriceBase,
  onIndexBudgetModel,
  onUpdateDocument,
  onDeleteDocument,
  onRefresh,
}: DocumentLibraryProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [docType, setDocType] = useState("auto");
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<KnowledgeIngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    variant?: "success" | "error" | "info";
  }>({
    open: false,
    title: "",
    message: "",
    variant: "info",
  });
  const [editItem, setEditItem] = useState<KnowledgeCatalogEntry | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editContentType, setEditContentType] = useState("");
  const [editDiscipline, setEditDiscipline] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeCatalogEntry | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [webUrl, setWebUrl] = useState("");
  const [webDocType, setWebDocType] = useState("auto");
  const [webForceOverwrite, setWebForceOverwrite] = useState(false);
  const [catalogQuery, setCatalogQuery] = useState("");
  const webImportJob = useKnowledgeWebImportOptional();
  const webImporting = webImportJob?.importing ?? false;
  const webProgress = webImportJob?.progress ?? null;
  const webResult = webImportJob?.resultSummary ?? null;
  const webImportError = webImportJob?.error ?? null;
  const webErrorsFromJob = webImportJob?.errors ?? [];

  const filteredCatalog = useMemo(() => {
    const priceTypes = new Set(["sinapi", "tcpo", "bases_precos", "orse", "cicro"]);
    const base = view === "catalog" ? catalog.filter((i) => !priceTypes.has(i.content_type)) : catalog;
    const q = catalogQuery.trim().toLowerCase();
    if (!q) return base;
    return base.filter((item) => {
      const hay = [
        item.name,
        item.filename,
        item.description,
        item.content_type,
        item.discipline?.join(" "),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [catalog, catalogQuery, view]);

  useEffect(() => {
    if (!webImportJob || webImportJob.importing) return;
    if (webImportJob.resultSummary) {
      setWebUrl("");
      setWebForceOverwrite(false);
      onRefresh?.();
    }
    if (webImportJob.error) {
      setError(webImportJob.error);
    }
  }, [webImportJob, onRefresh]);

  const pickFile = useCallback((incoming: File) => {
    setFile(incoming);
    setResult(null);
    setError(null);
    if (!name.trim()) {
      setName(incoming.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " "));
    }
  }, [name]);

  const openEdit = (item: KnowledgeCatalogEntry) => {
    setEditItem(item);
    setEditName(item.name || item.filename);
    setEditDescription(item.description || "");
    setEditContentType(item.content_type || "");
    setEditDiscipline(item.discipline?.[0] || "");
    setError(null);
  };

  const handleSaveEdit = async () => {
    if (!editItem || !onUpdateDocument) return;
    if (!editName.trim()) {
      setError("Informe um nome para o documento.");
      return;
    }
    setSavingEdit(true);
    setError(null);
    try {
      await onUpdateDocument(editItem.id, {
        name: editName.trim(),
        description: editDescription.trim(),
        content_type: editContentType || undefined,
        discipline: editDiscipline || undefined,
      });
      setEditItem(null);
      onRefresh?.();
      setDialog({
        open: true,
        title: "Documento atualizado",
        message: `"${editName.trim()}" foi salvo no catálogo.`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar alterações");
    } finally {
      setSavingEdit(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget || !onDeleteDocument) return;
    setDeleting(true);
    setError(null);
    try {
      await onDeleteDocument(deleteTarget.id);
      const name = deleteTarget.name || deleteTarget.filename;
      setDeleteTarget(null);
      onRefresh?.();
      setDialog({
        open: true,
        title: "Documento excluído",
        message: `"${name}" foi removido do catálogo, do banco de preços (se SINAPI) e dos índices da IA.`,
        variant: "success",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro ao excluir documento";
      setDeleteTarget(null);
      setDialog({
        open: true,
        title: "Falha ao excluir",
        message,
        variant: "error",
      });
    } finally {
      setDeleting(false);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    if (!onIngest) {
      setError("Upload não disponível nesta tela.");
      return;
    }
    if (!name.trim()) {
      setError("Informe um nome para o documento.");
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);

    const hint = resolveDocPreset(docType, options.document_type_presets ?? []);
    const formData = new FormData();
    formData.append("files", file);
    formData.append("name", name.trim());
    if (description.trim()) formData.append("description", description.trim());
    if (hint?.contentType) formData.append("content_type", hint.contentType);
    if (hint?.discipline) formData.append("discipline", hint.discipline);
    if (hint?.priceBase) formData.append("register_price_base", "true");
    if (hint?.budgetModel) formData.append("register_budget_model", "true");
    if (forceOverwrite) formData.append("force", "true");
    formData.append("auto_index", "true");

    try {
      const response = await onIngest(formData);
      setResult(response);
      const first = response.results[0];
      const success =
        response.ingested > 0 ||
        first?.status === "budget_model_attached" ||
        first?.status === "copied";

      if (success) {
        setFile(null);
        setName("");
        setDescription("");
        setDocType("auto");
        setForceOverwrite(false);
        if (inputRef.current) inputRef.current.value = "";
        onRefresh?.();
        const copied = response.results.find(
          (r) => r.status === "copied" || r.status === "budget_model_attached"
        );
        if (copied?.price_item_count) {
          setDialog({
            open: true,
            title: "Documento importado",
            message: `"${name.trim()}" salvo no catálogo com ${copied.price_item_count.toLocaleString("pt-BR")} itens de preço.`,
          });
        } else if (copied?.budget_model_indexed || copied?.status === "budget_model_attached") {
          setDialog({
            open: true,
            title: "Modelo de orçamento indexado",
            message:
              copied.reason ??
              `"${name.trim()}" — ${(copied.service_count ?? 0).toLocaleString("pt-BR")} serviços no WBS disponíveis para a IA.`,
          });
        } else if (copied?.storage_renamed && copied.saved_as) {
          setDialog({
            open: true,
            title: "Documento importado",
            message:
              copied.reason ??
              `Salvo como «${copied.saved_as}» (nome original já usado por outro documento no catálogo).`,
          });
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no upload");
    } finally {
      setUploading(false);
    }
  };

  const handleWebImport = async () => {
    if (!webUrl.trim()) return;
    if (!webImportJob) {
      setError("Importação web indisponível nesta tela.");
      return;
    }

    setError(null);
    webImportJob.clearResult();

    const hint = resolveDocPreset(webDocType, options.document_type_presets ?? []);
    webImportJob.startImport({
      page_url: webUrl.trim(),
      ...(hint?.contentType ? { content_type: hint.contentType } : {}),
      ...(hint?.discipline ? { discipline: hint.discipline } : {}),
      force: webForceOverwrite,
    });
  };

  const showUpload = view === "all" || view === "import";
  const showWeb = (view === "all" || view === "import") && !!webImportJob;
  const showCatalog = view === "all" || view === "catalog";

  return (
    <>
      {showUpload && (
      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h2 className="mb-1 text-base font-semibold text-white">
          {view === "import" ? "Upload de arquivo" : "Biblioteca de documentos"}
        </h2>
        <p className="mb-6 text-sm text-slate-500">
          {view === "import"
            ? "Envie um PDF, DOCX, Excel ou outro formato suportado. A indexação FAISS roda automaticamente após a ingestão."
            : "Um único local para NBRs, bases de preço (SINAPI/TCPO), modelos de orçamento PPD, projetos, catálogos e manuais. Se o PPD tiver o mesmo nome de outro documento (ex.: base de preços + modelo WBS), o sistema salva com nome único automaticamente. Tudo fica no catálogo central (catalog.jsonl) com sidecar para acesso rápido pela IA."}
        </p>

        <div className="mb-4 grid gap-4 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="mb-1.5 block text-xs font-medium text-slate-400">Nome *</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex: NBR 6118, SINAPI Mar/2026, Memorial passarela..."
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
            />
          </label>
          <label className="block sm:col-span-2">
            <span className="mb-1.5 block text-xs font-medium text-slate-400">Descrição</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="Opcional — contexto para você e para a IA"
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-400">Tipo de documento</span>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="auto">Detectar automaticamente</option>
              {presetSelectOptions(options.document_type_presets ?? [])}
            </select>
          </label>
          <label className="flex items-center gap-2 sm:col-span-2">
            <input
              type="checkbox"
              checked={forceOverwrite}
              onChange={(e) => setForceOverwrite(e.target.checked)}
              className="rounded border-slate-600 bg-slate-900 text-cyan-500"
            />
            <span className="text-xs text-slate-400">
              Substituir arquivo existente (mesmo nome no disco)
            </span>
          </label>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files[0];
            if (f) pickFile(f);
          }}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition",
            dragOver
              ? "border-cyan-400 bg-cyan-500/10"
              : "border-slate-700 bg-slate-950/40 hover:border-slate-500"
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) pickFile(f);
              e.target.value = "";
            }}
          />
          {file ? (
            <div>
              <p className="font-medium text-slate-200">{file.name}</p>
              <p className="mt-1 text-sm text-slate-500">{formatBytes(file.size)}</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-slate-300">Arraste ou clique para selecionar um arquivo</p>
              <p className="mt-1 text-xs text-slate-500">PDF, Excel, CSV, PPD (.xlsm), DOCX, JSON, XML…</p>
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleUpload}
            disabled={uploading || !file || !name.trim()}
            className="rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {uploading ? "Importando e indexando…" : "Importar documento"}
          </button>
          {file && (
            <button
              type="button"
              onClick={() => {
                setFile(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
              className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white"
            >
              Limpar arquivo
            </button>
          )}
        </div>

        {error && (
          <div className="mt-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-4 space-y-2 rounded-xl bg-slate-950/60 p-4 text-sm ring-1 ring-slate-800">
            <div>
              <span className={result.ingested > 0 ? "text-emerald-400" : "text-amber-400"}>
                {result.ingested > 0
                  ? `✓ ${result.ingested} importado(s)`
                  : `⊘ ${result.skipped} ignorado(s) — nenhum arquivo novo`}
              </span>
              {result.errors.length > 0 && (
                <span className="ml-3 text-red-400">✗ {result.errors.length} erro(s)</span>
              )}
            </div>
            {result.results.map((r) => (
              <p
                key={`${r.filename}-${r.status}`}
                className={cn(
                  "text-xs",
                  r.status === "copied" || r.status === "budget_model_attached"
                    ? "text-emerald-400/90"
                    : r.status.startsWith("skipped")
                      ? "text-amber-300/90"
                      : "text-red-300"
                )}
              >
                {r.filename}: {r.status}
                {r.reason ? ` — ${r.reason}` : ""}
                {r.saved_as ? ` → ${r.saved_as}` : ""}
                {r.budget_model_indexed
                  ? ` (${r.service_count ?? 0} serviços WBS)`
                  : ""}
              </p>
            ))}
          </div>
        )}
      </section>
      )}

      {showWeb && (
        <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
          <h2 className="mb-1 text-base font-semibold text-white">Importar de site (lote)</h2>
          <p className="mb-4 text-sm text-slate-500">
            Cole a URL da <strong className="text-slate-400">página que lista os anexos</strong> (tabela
            com Nome + Baixar ou links diretos para PDF/DOCX). Use o endereço completo da listagem, não
            a home do site.
          </p>
          <div className="mb-4 grid gap-4 sm:grid-cols-2">
            <label className="block sm:col-span-2">
              <span className="mb-1.5 block text-xs font-medium text-slate-400">URL da página *</span>
              <input
                type="url"
                value={webUrl}
                onChange={(e) => setWebUrl(e.target.value)}
                placeholder="https://…/ver-anexos/175"
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="mb-1.5 block text-xs font-medium text-slate-400">Tipo de documento</span>
              <select
                value={webDocType}
                onChange={(e) => setWebDocType(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
              >
                <option value="auto">Detectar automaticamente</option>
                {presetSelectOptions(options.document_type_presets ?? [])}
              </select>
              {webDocType !== "auto" && (() => {
                const hint = resolveDocPreset(webDocType, options.document_type_presets ?? []);
                if (!hint) return null;
                return (
                  <p className="mt-1.5 text-xs text-slate-500">
                    Disciplina: <span className="text-slate-400">{hint.discipline}</span>
                    {" · "}
                    Tipo: <span className="text-slate-400">{hint.contentType}</span>
                  </p>
                );
              })()}
            </label>
            <label className="flex items-center gap-2 sm:col-span-2">
              <input
                type="checkbox"
                checked={webForceOverwrite}
                onChange={(e) => setWebForceOverwrite(e.target.checked)}
                className="rounded border-slate-600 bg-slate-900 text-amber-500"
              />
              <span className="text-xs text-slate-400">
                Forçar reimportação (substituir arquivos já existentes)
              </span>
            </label>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={webImporting || !webUrl.trim()}
              onClick={handleWebImport}
              className="rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {webImporting ? "Importando…" : "Importar todos"}
            </button>
          </div>
          {(webImporting || webProgress) && (
            <div className="mt-4 space-y-2 rounded-xl bg-slate-950/50 p-4 ring-1 ring-slate-800">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="min-w-0 truncate text-slate-300">
                  {webProgress?.message ?? "Processando…"}
                </span>
                <span className="shrink-0 font-medium tabular-nums text-amber-300">
                  {webProgress?.percent ?? 0}%
                </span>
              </div>
              <div
                className="h-2.5 overflow-hidden rounded-full bg-slate-800"
                role="progressbar"
                aria-valuenow={webProgress?.percent ?? 0}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Progresso da importação web"
              >
                <div
                  className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-500 transition-[width] duration-300 ease-out"
                  style={{ width: `${webProgress?.percent ?? 0}%` }}
                />
              </div>
              {webProgress?.name && (
                <p className="truncate text-xs text-slate-500" title={webProgress.name}>
                  {webProgress.name}
                </p>
              )}
            </div>
          )}
          {webResult && (
            <p className={`mt-3 text-sm ${webErrorsFromJob.length && !webResult.startsWith("0") ? "text-emerald-400" : webErrorsFromJob.length ? "text-amber-300" : "text-emerald-400"}`}>
              {webResult}
            </p>
          )}
          {webImportError && !webImporting && (
            <p className="mt-3 text-sm text-red-300">{webImportError}</p>
          )}
          {webErrorsFromJob.length > 0 && (
            <ul className="mt-2 space-y-1 rounded-lg bg-red-500/10 p-3 text-xs text-red-300 ring-1 ring-red-500/20">
              {webErrorsFromJob.slice(0, 5).map((e, i) => (
                <li key={i}>
                  {e.stage ? `[${e.stage}] ` : ""}
                  {e.error}
                  {e.url ? ` — ${e.url}` : ""}
                </li>
              ))}
              {webErrorsFromJob.length > 5 && (
                <li>… e mais {webErrorsFromJob.length - 5} erro(s)</li>
              )}
            </ul>
          )}
        </section>
      )}

      {showCatalog && (
      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        {error && (
          <div className="mb-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
            {error}
          </div>
        )}
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">
              Catálogo ({filteredCatalog.length}
              {catalogQuery.trim() ? ` de ${catalog.length}` : ""}
              {stats?.catalog_total && catalog.length < stats.catalog_total
                ? ` · ${catalog.length.toLocaleString("pt-BR")}/${stats.catalog_total.toLocaleString("pt-BR")} carregados`
                : ""}
              )
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Pesquise por nome, número/ano (ex.: “6118”, “2019”, “IT”), arquivo, tipo ou disciplina.
              {view === "catalog" && (
                <> SINAPI/TCPO não aparecem aqui — use Configurações → Bases de preços.</>
              )}
            </p>
          </div>
          <label className="w-full sm:max-w-md">
            <span className="sr-only">Pesquisar no catálogo</span>
            <div className="relative">
              <input
                type="search"
                value={catalogQuery}
                onChange={(e) => setCatalogQuery(e.target.value)}
                placeholder="Pesquisar no catálogo…"
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 pr-9 text-sm text-white focus:border-cyan-500 focus:outline-none"
              />
              {catalogQuery.trim() && (
                <button
                  type="button"
                  onClick={() => setCatalogQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-1 text-slate-400 hover:text-white"
                  aria-label="Limpar pesquisa"
                >
                  ×
                </button>
              )}
            </div>
          </label>
        </div>
        {catalog.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">Nenhum documento importado ainda.</p>
        ) : filteredCatalog.length === 0 ? (
          <div className="rounded-xl bg-slate-950/40 p-6 text-center ring-1 ring-slate-800">
            <p className="text-sm text-slate-300">Nenhum resultado para “{catalogQuery.trim()}”.</p>
            <p className="mt-1 text-xs text-slate-500">Tente buscar só pelo número (ex.: 6118) ou por uma palavra-chave.</p>
          </div>
        ) : (
          <div className="max-h-[28rem] overflow-y-auto overflow-x-hidden rounded-xl ring-1 ring-slate-800">
            <table className="w-full table-fixed text-left text-sm">
              <thead className="sticky top-0 bg-slate-950/95 text-xs uppercase text-slate-500">
                <tr className="border-b border-slate-800">
                  <th className="px-4 py-3 font-medium">Nome</th>
                  <th className="w-28 px-4 py-3 font-medium">Tipo</th>
                  <th className="w-40 px-4 py-3 font-medium">Preços</th>
                  <th className="w-28 px-4 py-3 font-medium">Data</th>
                  <th className="w-60 px-4 py-3 font-medium">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredCatalog.map((item) => (
                  <tr key={item.id || item.path} className="hover:bg-slate-800/30">
                    <td className="min-w-0 px-4 py-3 align-top">
                      <p className="break-words font-medium text-slate-200">
                        {item.name || item.filename}
                      </p>
                      {item.description && (
                        <p className="mt-0.5 line-clamp-2 break-words text-xs text-slate-500">
                          {item.description}
                        </p>
                      )}
                      <p className="mt-0.5 truncate text-xs text-slate-600" title={item.filename}>
                        {item.filename}
                      </p>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                        {item.content_type}
                      </span>
                      {item.has_budget_model && (
                        <span className="ml-1 rounded bg-violet-600/20 px-2 py-0.5 text-xs text-violet-300">
                          WBS
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 align-top text-xs text-slate-400">
                      {item.has_price_items ? (
                        <span className="text-emerald-400">
                          {item.price_item_count?.toLocaleString("pt-BR")} itens
                          {item.is_active_price_base && " · ativa"}
                        </span>
                      ) : item.has_budget_model ? (
                        <span className="text-violet-300">
                          {(item.service_count ?? 0).toLocaleString("pt-BR")} serviços WBS
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 align-top text-xs text-slate-500">
                      {item.catalog_ts ? formatDate(item.catalog_ts) : "—"}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <div className="flex flex-wrap gap-1">
                        {onUpdateDocument && (
                          <button
                            type="button"
                            onClick={() => openEdit(item)}
                            className="rounded bg-slate-700/60 px-2 py-1 text-xs text-slate-300 ring-1 ring-slate-600/50 hover:bg-slate-700"
                          >
                            Editar
                          </button>
                        )}
                        {onDeleteDocument && (
                          <button
                            type="button"
                            onClick={() => setDeleteTarget(item)}
                            className="rounded bg-red-600/15 px-2 py-1 text-xs text-red-300 ring-1 ring-red-500/30 hover:bg-red-600/25"
                          >
                            Excluir
                          </button>
                        )}
                        {item.has_price_items && onActivatePriceBase && !item.is_active_price_base && (
                          <button
                            type="button"
                            onClick={() => onActivatePriceBase(item.id)}
                            className="rounded bg-cyan-600/20 px-2 py-1 text-xs text-cyan-300 ring-1 ring-cyan-500/40 hover:bg-cyan-600/30"
                          >
                            Usar no orçamento
                          </button>
                        )}
                        {onIndexBudgetModel &&
                          /\.(xlsm|xlsx|xls)$/i.test(item.filename) &&
                          !item.has_budget_model && (
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  const res = await onIndexBudgetModel(item.id);
                                  setDialog({
                                    open: true,
                                    title: "Modelo WBS indexado",
                                    message:
                                      res.reason ??
                                      `${res.service_count} serviços extraídos do PPD para a IA.`,
                                  });
                                } catch (err) {
                                  setError(
                                    err instanceof Error ? err.message : "Erro ao indexar WBS"
                                  );
                                }
                              }}
                              className="rounded bg-violet-600/20 px-2 py-1 text-xs text-violet-300 ring-1 ring-violet-500/40 hover:bg-violet-600/30"
                            >
                              Indexar WBS
                            </button>
                          )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(view === "catalog" || view === "all") && (
          <KnowledgeCatalogStatsCards stats={stats} catalog={catalog} options={options} />
        )}
      </section>
      )}

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        variant={dialog.variant ?? "success"}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
      />

      {editItem && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-xl bg-slate-900 p-6 ring-1 ring-slate-700">
            <h3 className="text-lg font-semibold text-white">Editar documento</h3>
            <p className="mt-1 text-xs text-slate-500">{editItem.filename}</p>
            <div className="mt-4 space-y-4">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-slate-400">Nome *</span>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-slate-400">Descrição</span>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
                />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-slate-400">Tipo</span>
                  <select
                    value={editContentType}
                    onChange={(e) => setEditContentType(e.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
                  >
                    <option value="">Manter atual</option>
                    {options.content_types.map((ct) => (
                      <option key={ct.value} value={ct.value}>
                        {ct.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-slate-400">Disciplina</span>
                  <select
                    value={editDiscipline}
                    onChange={(e) => setEditDiscipline(e.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
                  >
                    <option value="">Manter atual</option>
                    {options.disciplines.map((d) => (
                      <option key={d.value} value={d.value}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditItem(null)}
                disabled={savingEdit}
                className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                disabled={savingEdit || !editName.trim()}
                className="rounded-lg bg-cyan-600/30 px-4 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-600/40 disabled:opacity-50"
              >
                {savingEdit ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      <ActionDialog
        open={!!deleteTarget}
        title="Excluir documento"
        message={
          deleteTarget
            ? `Remover "${deleteTarget.name || deleteTarget.filename}" do catálogo?\n\nO arquivo, metadados, índice FAISS e banco SINAPI (se aplicável) serão apagados.${
                deleteTarget.is_active_price_base
                  ? "\n\nEste documento é a base de preços ativa — será desativada."
                  : ""
              }`
            : ""
        }
        variant="confirm"
        destructive
        confirmLabel={deleting ? "Excluindo…" : "Excluir"}
        onConfirm={deleting ? undefined : () => void handleConfirmDelete()}
        onCancel={() => !deleting && setDeleteTarget(null)}
      />
    </>
  );
}
