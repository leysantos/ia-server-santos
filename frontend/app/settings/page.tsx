"use client";

import { useCallback, useEffect, useState } from "react";
import KnowledgeUploader from "@/components/KnowledgeUploader";
import LoadingSpinner from "@/components/LoadingSpinner";
import { api } from "@/services/api";
import type {
  KnowledgeCatalogResponse,
  KnowledgeOptionsResponse,
  KnowledgeStatsResponse,
} from "@/types/api";
import { cn, formatDate } from "@/lib/utils";

const BASE_COLORS: Record<string, string> = {
  nbr: "from-blue-500/20 to-blue-600/10 ring-blue-500/30 text-blue-300",
  sinapi: "from-emerald-500/20 to-emerald-600/10 ring-emerald-500/30 text-emerald-300",
  tcpo: "from-amber-500/20 to-amber-600/10 ring-amber-500/30 text-amber-300",
  tdr: "from-purple-500/20 to-purple-600/10 ring-purple-500/30 text-purple-300",
  catalogos: "from-pink-500/20 to-pink-600/10 ring-pink-500/30 text-pink-300",
  regional: "from-teal-500/20 to-teal-600/10 ring-teal-500/30 text-teal-300",
};

const CATALOG_LIMIT_OPTIONS = [30, 50, 100, 500] as const;

function formatTime(date: Date): string {
  return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function SettingsPage() {
  const [options, setOptions] = useState<KnowledgeOptionsResponse | null>(null);
  const [stats, setStats] = useState<KnowledgeStatsResponse | null>(null);
  const [catalog, setCatalog] = useState<KnowledgeCatalogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [refreshNotice, setRefreshNotice] = useState<string | null>(null);
  const [catalogLimit, setCatalogLimit] = useState<number>(100);
  const [indexing, setIndexing] = useState<string | null>(null);
  const [indexResult, setIndexResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (opts?: { showSpinner?: boolean }) => {
    const showSpinner = opts?.showSpinner ?? false;
    setError(null);
    if (showSpinner) setRefreshing(true);
    try {
      const [optsRes, st, cat] = await Promise.all([
        api.knowledgeOptions(),
        api.knowledgeStats(),
        api.knowledgeCatalog(catalogLimit),
      ]);
      setOptions(optsRes);
      setStats(st);
      setCatalog(cat);
      const now = new Date();
      setLastRefreshed(now);
      setRefreshNotice(
        `Atualizado às ${formatTime(now)} · ${cat.total} documento${cat.total !== 1 ? "s" : ""} único${cat.total !== 1 ? "s" : ""}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar dados");
      setRefreshNotice(null);
    } finally {
      setLoading(false);
      if (showSpinner) setRefreshing(false);
    }
  }, [catalogLimit]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleCatalogRefresh = () => {
    refresh({ showSpinner: true });
  };

  const handleIndex = async (base?: string) => {
    setIndexing(base ?? "all");
    setIndexResult(null);
    try {
      const result = await api.knowledgeIndex(base, false);
      const errCount = result.errors.length;
      const baseSummary = base ? result.bases[base] : null;
      const baseErrors = baseSummary && typeof baseSummary === "object" && "errors" in baseSummary
        ? (baseSummary.errors as unknown[]).length
        : 0;
      const totalErrs = errCount + baseErrors;
      setIndexResult(
        base
          ? `Base ${base}: ${result.total_chunks} chunks indexados${totalErrs ? ` · ${totalErrs} erro(s)` : ""}`
          : `Total: ${result.total_chunks} chunks · ${result.total_chunks_in_store} no store${totalErrs ? ` · ${totalErrs} erro(s)` : ""}`
      );
      await refresh({ showSpinner: true });
    } catch (err) {
      setIndexResult(err instanceof Error ? err.message : "Erro na indexação");
    } finally {
      setIndexing(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <LoadingSpinner label="Carregando configurações..." size="lg" />
      </div>
    );
  }

  const indexChunks = stats?.index?.multi_index ?? {};
  const totalChunks = stats?.index?.total_multi_chunks ?? 0;
  const showingCount = catalog?.items.length ?? 0;
  const totalUnique = catalog?.total ?? 0;

  return (
    <>
      <header className="shrink-0 border-b border-slate-800/80 px-6 py-4">
        <h1 className="text-lg font-semibold text-white">Configurações do Sistema</h1>
        <p className="text-sm text-slate-500">
          Alimentar bases de conhecimento — NBR, SINAPI, TCPO e demais documentos
        </p>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-4xl space-y-8">
          {error && (
            <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
              {error}
            </div>
          )}

          {refreshNotice && !error && (
            <div
              className={cn(
                "rounded-xl px-4 py-2.5 text-sm ring-1 transition-all",
                refreshing
                  ? "bg-cyan-500/10 text-cyan-300 ring-cyan-500/30"
                  : "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
              )}
            >
              {refreshing ? "Atualizando catálogo e estatísticas…" : refreshNotice}
            </div>
          )}

          {/* Stats */}
          <section>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Status da base
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
                <p className="text-2xl font-bold text-white">{stats?.catalog_total ?? 0}</p>
                <p className="text-xs text-slate-500">Documentos únicos no catálogo</p>
                {(stats?.catalog_log_entries ?? 0) > (stats?.catalog_total ?? 0) && (
                  <p className="mt-1 text-xs text-slate-600">
                    {stats?.catalog_log_entries} entradas no log (re-uploads)
                  </p>
                )}
              </div>
              <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
                <p className="text-2xl font-bold text-cyan-400">{totalChunks}</p>
                <p className="text-xs text-slate-500">Chunks indexados (FAISS)</p>
              </div>
              {(options?.bases ?? []).slice(0, 2).map((base) => (
                <div
                  key={base.value}
                  className={cn(
                    "rounded-xl bg-gradient-to-br p-4 ring-1",
                    BASE_COLORS[base.value] ?? "from-slate-800/60 to-slate-900/60 ring-slate-700 text-slate-300"
                  )}
                >
                  <p className="text-2xl font-bold">{indexChunks[base.value] ?? 0}</p>
                  <p className="text-xs opacity-70">{base.label}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Upload */}
          <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
            <h2 className="mb-1 text-base font-semibold text-white">Upload em lote</h2>
            <p className="mb-6 text-sm text-slate-500">
              Selecione vários arquivos de uma vez. O sistema classifica, armazena e indexa automaticamente.
            </p>
            {options && (
              <KnowledgeUploader
                options={options}
                onIngest={(formData) => api.knowledgeIngest(formData)}
                onComplete={() => refresh({ showSpinner: true })}
              />
            )}
          </section>

          {/* Manual indexing */}
          <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
            <h2 className="mb-1 text-base font-semibold text-white">Indexação FAISS</h2>
            <p className="mb-4 text-sm text-slate-500">
              Reindexar bases manualmente após alterações no disco ou falhas parciais.
            </p>
            <div className="flex flex-wrap gap-2">
              {(options?.bases ?? []).map((base) => (
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
                  {indexing === base.value ? "Indexando…" : base.label}
                </button>
              ))}
              <button
                type="button"
                disabled={indexing !== null}
                onClick={() => handleIndex()}
                className="rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-300 ring-1 ring-cyan-500/40 hover:bg-cyan-500/30 disabled:opacity-50"
              >
                {indexing === "all" ? "Indexando tudo…" : "Indexar tudo"}
              </button>
            </div>
            {indexResult && (
              <p className="mt-3 text-sm text-slate-400">{indexResult}</p>
            )}
          </section>

          {/* Catalog */}
          <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-white">Catálogo de documentos</h2>
                <p className="text-sm text-slate-500">
                  Exibindo {showingCount} de {totalUnique} documento{totalUnique !== 1 ? "s" : ""} único
                  {totalUnique !== 1 ? "s" : ""}
                  {(catalog?.log_entries ?? 0) > totalUnique && (
                    <span className="text-slate-600">
                      {" "}
                      · log com {catalog?.log_entries} entradas (re-uploads)
                    </span>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={catalogLimit}
                  onChange={(e) => setCatalogLimit(Number(e.target.value))}
                  disabled={refreshing}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-300 focus:border-cyan-500 focus:outline-none disabled:opacity-50"
                  aria-label="Quantidade de documentos no catálogo"
                >
                  {CATALOG_LIMIT_OPTIONS.map((n) => (
                    <option key={n} value={n}>
                      Mostrar {n === 500 ? "todos" : n}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleCatalogRefresh}
                  disabled={refreshing}
                  className={cn(
                    "flex min-w-[7.5rem] items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-sm ring-1 transition disabled:opacity-60",
                    refreshing
                      ? "bg-cyan-500/15 text-cyan-300 ring-cyan-500/40"
                      : "bg-slate-800 text-slate-300 ring-slate-700 hover:bg-slate-700"
                  )}
                >
                  {refreshing ? (
                    <>
                      <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
                      Atualizando…
                    </>
                  ) : (
                    "Atualizar"
                  )}
                </button>
              </div>
            </div>
            {lastRefreshed && !refreshing && (
              <p className="mb-3 text-xs text-slate-600">
                Última sincronização: {formatDate(lastRefreshed.toISOString())} às {formatTime(lastRefreshed)}
              </p>
            )}
            {!catalog?.items.length ? (
              <p className="py-8 text-center text-sm text-slate-500">
                Nenhum documento no catálogo. Faça upload acima para começar.
              </p>
            ) : (
              <div className="max-h-[32rem] overflow-auto rounded-xl ring-1 ring-slate-800">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 z-10 bg-slate-950/95 backdrop-blur">
                    <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
                      <th className="px-4 py-3 font-medium">Arquivo</th>
                      <th className="px-4 py-3 font-medium">Tipo</th>
                      <th className="px-4 py-3 font-medium">Disciplina</th>
                      <th className="px-4 py-3 font-medium">Data</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {catalog.items.map((item) => (
                      <tr key={item.id || item.path} className="hover:bg-slate-800/30">
                        <td className="max-w-xs truncate px-4 py-3 text-slate-200" title={item.filename}>
                          {item.filename}
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                            {item.content_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-400">
                          {item.discipline.join(", ") || "—"}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                          {item.catalog_ts ? formatDate(item.catalog_ts) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {showingCount < totalUnique && (
              <p className="mt-3 text-xs text-amber-400/90">
                Há mais documentos no catálogo. Aumente &quot;Mostrar&quot; ou selecione &quot;todos&quot; para ver a lista completa.
              </p>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
