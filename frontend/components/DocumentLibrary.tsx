"use client";

import { useCallback, useRef, useState } from "react";
import ActionDialog from "@/components/ActionDialog";
import { cn, formatDate } from "@/lib/utils";
import type {
  KnowledgeCatalogEntry,
  KnowledgeIngestResponse,
  KnowledgeOptionsResponse,
} from "@/types/api";

const ACCEPT = ".pdf,.csv,.xlsx,.xls,.xlsm,.json,.md,.txt,.docx,.xml";

const TYPE_HINTS: Record<string, { contentType: string; discipline: string; priceBase: boolean; budgetModel?: boolean }> = {
  nbrs: { contentType: "nbrs", discipline: "ESTRUTURAL", priceBase: false },
  sinapi: { contentType: "sinapi", discipline: "ORÇAMENTO", priceBase: true },
  tcpo: { contentType: "tcpo", discipline: "ORÇAMENTO", priceBase: true },
  tdrs: { contentType: "tdrs", discipline: "GERAL", priceBase: false },
  catalogos: { contentType: "catalogos", discipline: "ARQUITETURA", priceBase: false },
  manuais: { contentType: "manuais", discipline: "GERAL", priceBase: false },
  projetos: { contentType: "projetos", discipline: "GERAL", priceBase: false },
  regional: { contentType: "regional", discipline: "MEIO_AMBIENTE", priceBase: false },
  modelos_orcamento: { contentType: "modelos_orcamento", discipline: "ORÇAMENTO", priceBase: false, budgetModel: true },
  auto: { contentType: "", discipline: "", priceBase: false },
};

interface DocumentLibraryProps {
  options: KnowledgeOptionsResponse;
  catalog: KnowledgeCatalogEntry[];
  onIngest: (formData: FormData) => Promise<KnowledgeIngestResponse>;
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
  options,
  catalog,
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
  const [dialog, setDialog] = useState<{ open: boolean; title: string; message: string }>({
    open: false,
    title: "",
    message: "",
  });
  const [editItem, setEditItem] = useState<KnowledgeCatalogEntry | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editContentType, setEditContentType] = useState("");
  const [editDiscipline, setEditDiscipline] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeCatalogEntry | null>(null);
  const [deleting, setDeleting] = useState(false);

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
        message: `"${name}" foi removido do catálogo e dos índices da IA.`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir documento");
    } finally {
      setDeleting(false);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    if (!name.trim()) {
      setError("Informe um nome para o documento.");
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);

    const hint = TYPE_HINTS[docType] ?? TYPE_HINTS.auto;
    const formData = new FormData();
    formData.append("files", file);
    formData.append("name", name.trim());
    if (description.trim()) formData.append("description", description.trim());
    if (hint.contentType) formData.append("content_type", hint.contentType);
    if (hint.discipline) formData.append("discipline", hint.discipline);
    if (hint.priceBase) formData.append("register_price_base", "true");
    if (hint.budgetModel) formData.append("register_budget_model", "true");
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

  return (
    <>
      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h2 className="mb-1 text-base font-semibold text-white">Biblioteca de documentos</h2>
        <p className="mb-6 text-sm text-slate-500">
          Um único local para NBRs, bases de preço (SINAPI/TCPO), modelos de orçamento PPD, projetos, catálogos e manuais.
          Se o PPD tiver o mesmo nome de outro documento (ex.: base de preços + modelo WBS), o sistema salva com nome único automaticamente.
          Tudo fica no catálogo central (<code className="text-slate-400">catalog.jsonl</code>) com sidecar
          para acesso rápido pela IA.
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
              {options.content_types.map((ct) => (
                <option key={ct.value} value={ct.value}>
                  {ct.label}
                </option>
              ))}
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

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h3 className="mb-4 text-base font-semibold text-white">Catálogo ({catalog.length})</h3>
        {catalog.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">Nenhum documento importado ainda.</p>
        ) : (
          <div className="max-h-[28rem] overflow-auto rounded-xl ring-1 ring-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-slate-950/95 text-xs uppercase text-slate-500">
                <tr className="border-b border-slate-800">
                  <th className="px-4 py-3 font-medium">Nome</th>
                  <th className="px-4 py-3 font-medium">Tipo</th>
                  <th className="px-4 py-3 font-medium">Preços</th>
                  <th className="px-4 py-3 font-medium">Data</th>
                  <th className="px-4 py-3 font-medium">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {catalog.map((item) => (
                  <tr key={item.id || item.path} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-200">{item.name || item.filename}</p>
                      {item.description && (
                        <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{item.description}</p>
                      )}
                      <p className="mt-0.5 truncate text-xs text-slate-600" title={item.filename}>
                        {item.filename}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                        {item.content_type}
                      </span>
                      {item.has_budget_model && (
                        <span className="ml-1 rounded bg-violet-600/20 px-2 py-0.5 text-xs text-violet-300">
                          WBS
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
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
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                      {item.catalog_ts ? formatDate(item.catalog_ts) : "—"}
                    </td>
                    <td className="px-4 py-3">
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
      </section>

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        variant="success"
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
            ? `Remover "${deleteTarget.name || deleteTarget.filename}" do catálogo?\n\nO arquivo, metadados e trechos no índice FAISS serão apagados.${
                deleteTarget.is_active_price_base
                  ? "\n\nEste documento é a base de preços ativa — será desativada."
                  : ""
              }`
            : ""
        }
        variant="confirm"
        confirmLabel={deleting ? "Excluindo…" : "Excluir"}
        onConfirm={deleting ? undefined : handleConfirmDelete}
        onCancel={() => !deleting && setDeleteTarget(null)}
      />
    </>
  );
}
