"use client";

import { useCallback, useEffect, useState } from "react";
import DocumentLibrary from "@/components/DocumentLibrary";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import { api } from "@/services/api";
import type {
  KnowledgeCatalogResponse,
  KnowledgeOptionsResponse,
  KnowledgeStatsResponse,
} from "@/types/api";
import { cn } from "@/lib/utils";

const BASE_COLORS: Record<string, string> = {
  nbr: "from-blue-500/20 to-blue-600/10 ring-blue-500/30 text-blue-300",
  sinapi: "from-emerald-500/20 to-emerald-600/10 ring-emerald-500/30 text-emerald-300",
  tcpo: "from-amber-500/20 to-amber-600/10 ring-amber-500/30 text-amber-300",
};

export default function SettingsPage() {
  const [options, setOptions] = useState<KnowledgeOptionsResponse | null>(null);
  const [stats, setStats] = useState<KnowledgeStatsResponse | null>(null);
  const [catalog, setCatalog] = useState<KnowledgeCatalogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [indexing, setIndexing] = useState<string | null>(null);
  const [indexResult, setIndexResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [optsRes, st, cat] = await Promise.all([
        api.knowledgeOptions(),
        api.knowledgeStats(),
        api.knowledgeCatalog(200),
      ]);
      setOptions(optsRes);
      setStats(st);
      setCatalog(cat);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleIndex = async (base?: string) => {
    setIndexing(base ?? "all");
    setIndexResult(null);
    try {
      const result = await api.knowledgeIndex(base, false);
      setIndexResult(
        base
          ? `Base ${base}: ${result.total_chunks} chunks indexados`
          : `Total: ${result.total_chunks} chunks no índice`
      );
      await refresh();
    } catch (err) {
      setIndexResult(err instanceof Error ? err.message : "Erro na indexação");
    } finally {
      setIndexing(null);
    }
  };

  const handleActivatePriceBase = async (documentId: string) => {
    await api.knowledgeActivatePriceBase(documentId);
    await refresh();
  };

  const handleIndexBudgetModel = async (documentId: string) => {
    const result = await api.knowledgeIndexBudgetModel(documentId);
    await refresh();
    return result;
  };

  const handleUpdateDocument = async (
    documentId: string,
    payload: { name?: string; description?: string; content_type?: string; discipline?: string }
  ) => {
    await api.knowledgeUpdateDocument(documentId, payload);
    await refresh();
  };

  const handleDeleteDocument = async (documentId: string) => {
    await api.knowledgeDeleteDocument(documentId);
    await refresh();
  };

  if (loading || !options) {
    return (
      <>
        <ShellHeader className="px-6" showModelsStatus>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-white">Configurações</h1>
            <p className="text-sm text-slate-500">Carregando…</p>
          </div>
        </ShellHeader>
        <div className="flex flex-1 items-center justify-center">
          <LoadingSpinner label="Carregando configurações..." size="lg" />
        </div>
      </>
    );
  }

  const indexChunks = stats?.index?.multi_index ?? {};
  const totalChunks = stats?.index?.total_multi_chunks ?? 0;

  return (
    <>
      <ShellHeader className="px-6" showModelsStatus>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Configurações</h1>
          <p className="text-sm text-slate-500">
            Biblioteca unificada — NBRs, bases de preço, projetos, catálogos e demais documentos
          </p>
        </div>
      </ShellHeader>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-8">
          {error && (
            <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
              {error}
            </div>
          )}

          <section>
            <div className="mb-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
                <p className="text-2xl font-bold text-white">{stats?.catalog_total ?? 0}</p>
                <p className="text-xs text-slate-500">Documentos no catálogo</p>
              </div>
              <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
                <p className="text-2xl font-bold text-cyan-400">{totalChunks}</p>
                <p className="text-xs text-slate-500">Chunks FAISS (IA)</p>
              </div>
              <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
                <p className="text-2xl font-bold text-emerald-400">
                  {catalog?.items.filter((i) => i.has_price_items).length ?? 0}
                </p>
                <p className="text-xs text-slate-500">Bases de preço</p>
              </div>
            </div>
          </section>

          <DocumentLibrary
            options={options}
            catalog={catalog?.items ?? []}
            onIngest={(formData) => api.knowledgeIngest(formData)}
            onActivatePriceBase={handleActivatePriceBase}
            onIndexBudgetModel={handleIndexBudgetModel}
            onUpdateDocument={handleUpdateDocument}
            onDeleteDocument={handleDeleteDocument}
            onRefresh={refresh}
          />

          <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
            <h2 className="mb-1 text-base font-semibold text-white">Reindexar FAISS</h2>
            <p className="mb-4 text-sm text-slate-500">
              Use apenas se a indexação automática falhar ou após alterações manuais no disco.
            </p>
            <div className="flex flex-wrap gap-2">
              {(options.bases ?? []).map((base) => (
                <button
                  key={base.value}
                  type="button"
                  disabled={indexing !== null}
                  onClick={() => handleIndex(base.value)}
                  className={cn(
                    "rounded-lg px-4 py-2 text-sm font-medium ring-1 transition disabled:opacity-50",
                    BASE_COLORS[base.value] ?? "bg-slate-800 text-slate-300 ring-slate-700"
                  )}
                >
                  {indexing === base.value ? "Indexando…" : `${base.label} (${indexChunks[base.value] ?? 0})`}
                </button>
              ))}
              <button
                type="button"
                disabled={indexing !== null}
                onClick={() => handleIndex()}
                className="rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-300 ring-1 ring-cyan-500/40 disabled:opacity-50"
              >
                {indexing === "all" ? "Indexando tudo…" : "Indexar tudo"}
              </button>
            </div>
            {indexResult && <p className="mt-3 text-sm text-slate-400">{indexResult}</p>}
          </section>
        </div>
      </div>
    </>
  );
}
