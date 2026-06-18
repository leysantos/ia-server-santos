"use client";

import { useCallback, useEffect, useState } from "react";
import JsonViewer from "@/components/JsonViewer";
import LoadingSpinner from "@/components/LoadingSpinner";
import { api } from "@/services/api";
import type { HistoryItem } from "@/types/api";
import { formatDate } from "@/lib/utils";

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<HistoryItem | null>(null);
  const [limit, setLimit] = useState(50);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.history(limit);
      setItems(response.items);
      if (response.items.length > 0) {
        setSelected((prev) => prev ?? response.items[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar histórico");
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  return (
    <>
      <header className="flex shrink-0 items-center justify-between border-b border-slate-800/80 px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-white">Histórico</h1>
          <p className="text-sm text-slate-500">
            Interações persistidas no PostgreSQL
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-300 focus:border-cyan-500 focus:outline-none"
          >
            {[10, 25, 50, 100].map((n) => (
              <option key={n} value={n}>
                Últimos {n}
              </option>
            ))}
          </select>
          <button
            onClick={loadHistory}
            disabled={loading}
            className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-slate-300 ring-1 ring-slate-700 hover:bg-slate-700 disabled:opacity-50"
          >
            Atualizar
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {loading && items.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <LoadingSpinner label="Carregando histórico..." size="lg" />
          </div>
        ) : error ? (
          <div className="flex flex-1 items-center justify-center p-6">
            <div className="max-w-md rounded-xl bg-red-500/10 px-6 py-4 text-center text-sm text-red-300 ring-1 ring-red-500/30">
              {error}
            </div>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-1 items-center justify-center p-6 text-slate-500">
            Nenhuma interação registrada ainda.
          </div>
        ) : (
          <>
            <div className="w-80 shrink-0 overflow-y-auto border-r border-slate-800/80">
              {items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSelected(item)}
                  className={`w-full border-b border-slate-800/60 px-4 py-4 text-left transition hover:bg-slate-800/40 ${
                    selected?.id === item.id ? "bg-cyan-500/5 ring-inset ring-cyan-500/20" : ""
                  }`}
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        item.mode === "multi"
                          ? "bg-purple-500/15 text-purple-300"
                          : "bg-cyan-500/15 text-cyan-300"
                      }`}
                    >
                      {item.mode === "multi" ? "Multi" : "Chat"}
                    </span>
                    <span className="text-xs text-slate-600">
                      {formatDate(item.created_at)}
                    </span>
                  </div>
                  <p className="line-clamp-2 text-sm text-slate-300">{item.input_text}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {(item.agent_runs?.length ?? 0)} execuções
                  </p>
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {selected && (
                <div className="mx-auto max-w-4xl space-y-6">
                  <div>
                    <h2 className="text-lg font-semibold text-white">Detalhes</h2>
                    <p className="mt-1 text-sm text-slate-400">{selected.input_text}</p>
                  </div>

                  {(selected.agent_runs?.length ?? 0) > 0 && (
                    <section>
                      <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                        Execuções de agentes
                      </h3>
                      <div className="space-y-3">
                        {selected.agent_runs?.map((run) => (
                          <div
                            key={run.id}
                            className="rounded-xl bg-slate-800/40 p-4 ring-1 ring-slate-700/60"
                          >
                            <div className="mb-2 flex flex-wrap gap-2 text-xs">
                              <span className="text-cyan-300">{run.discipline}</span>
                              <span className="text-slate-500">{run.agent_name}</span>
                              {run.had_context && (
                                <span className="rounded bg-emerald-500/15 px-1.5 text-emerald-400">
                                  RAG
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-slate-300">{run.result_text}</p>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}

                  {(selected.orchestrator_logs?.length ?? 0) > 0 && (
                    <section>
                      <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                        Logs do orquestrador
                      </h3>
                      {selected.orchestrator_logs?.map((log) => (
                        <div key={log.id} className="space-y-3">
                          <div className="flex flex-wrap gap-2">
                            {log.disciplines?.map((d) => (
                              <span
                                key={d}
                                className="rounded-full bg-purple-500/10 px-2 py-0.5 text-xs text-purple-300"
                              >
                                {d}
                              </span>
                            ))}
                          </div>
                          {log.final_report && (
                            <div className="rounded-xl bg-slate-800/40 p-4 text-sm text-slate-300 whitespace-pre-wrap ring-1 ring-slate-700/60">
                              {log.final_report.slice(0, 1500)}
                              {log.final_report.length > 1500 && "..."}
                            </div>
                          )}
                        </div>
                      ))}
                    </section>
                  )}

                  <JsonViewer data={selected} title="Payload completo" />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
