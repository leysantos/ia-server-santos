"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import LoadingSpinner from "@/components/LoadingSpinner";
import PipelineSteps, { type PipelineStep } from "@/components/PipelineSteps";
import ShellHeader from "@/components/ShellHeader";
import { api } from "@/services/api";
import type { ConsoleLogItem, ConsoleStatsResponse } from "@/types/api";
import { formatDate } from "@/lib/utils";

export default function ConsolePage() {
  const [logs, setLogs] = useState<ConsoleLogItem[]>([]);
  const [stats, setStats] = useState<ConsoleStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [logsRes, statsRes] = await Promise.all([
        api.consoleLogs(50),
        api.consoleStats(),
      ]);
      setLogs(logsRes.items);
      setStats(statsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar console");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const pipelineForLog = (log: ConsoleLogItem): PipelineStep[] => {
    const steps: PipelineStep[] = [
      { id: "decompose", label: "Decomposição", status: "done" },
    ];
    for (const d of log.disciplines) {
      const run = log.agent_runs.find((r) => r.discipline === d);
      steps.push({
        id: `agent-${d}`,
        label: d,
        status: run ? "done" : "pending",
        detail: run?.agent_name ?? undefined,
      });
    }
    steps.push({
      id: "synthesis",
      label: "Síntese",
      status: log.final_report ? "done" : "pending",
    });
    return steps;
  };

  return (
    <>
      <ShellHeader className="px-6" showModelsStatus>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Orchestrator Console</h1>
          <p className="text-sm text-slate-500">
            Logs read-only de orquestrações e execuções de agentes
          </p>
        </div>
      </ShellHeader>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {stats && (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Orquestrações", value: stats.orchestrator_logs },
              { label: "Agent runs", value: stats.agent_runs },
              { label: "Eventos", value: stats.activity_events },
              { label: "Decisões", value: stats.decisions },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-xl bg-slate-900/50 px-4 py-3 ring-1 ring-slate-800/80"
              >
                <p className="text-xs text-slate-500">{s.label}</p>
                <p className="text-xl font-semibold text-white">{s.value}</p>
              </div>
            ))}
          </div>
        )}

        {loading && (
          <div className="flex justify-center py-16">
            <LoadingSpinner label="Carregando logs..." />
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
            {error}
          </div>
        )}

        {!loading && !error && (
          <div className="mx-auto max-w-5xl space-y-4">
            {logs.length === 0 ? (
              <p className="text-center text-sm text-slate-500">
                Nenhuma orquestração registrada. Use{" "}
                <Link href="/orchestrate" className="text-cyan-400 hover:underline">
                  /orchestrate
                </Link>
                .
              </p>
            ) : (
              logs.map((log) => (
                <article
                  key={log.id}
                  className="rounded-xl bg-slate-900/40 p-4 ring-1 ring-slate-800/80"
                >
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-white line-clamp-2">
                        {log.input_text}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {log.created_at ? formatDate(log.created_at) : "—"} ·{" "}
                        {log.agent_count} agente(s) · RAG {log.use_rag ? "on" : "off"}
                      </p>
                    </div>
                    {log.project_id && (
                      <Link
                        href={`/projects/${log.project_id}/activity`}
                        className="shrink-0 text-xs text-cyan-500 hover:text-cyan-400"
                      >
                        Projeto
                      </Link>
                    )}
                  </div>

                  <PipelineSteps steps={pipelineForLog(log)} className="mb-3" />

                  <button
                    type="button"
                    onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                    className="text-xs text-slate-400 hover:text-cyan-400"
                  >
                    {expanded === log.id ? "Ocultar detalhes" : "Ver detalhes"}
                  </button>

                  {expanded === log.id && (
                    <div className="mt-3 space-y-3 border-t border-slate-800/80 pt-3">
                      {log.agent_runs.map((run) => (
                        <div
                          key={run.id}
                          className="rounded-lg bg-slate-950/50 p-3 text-sm"
                        >
                          <p className="font-medium text-cyan-300">
                            {run.discipline ?? "—"} · {run.agent_name ?? "agente"}
                          </p>
                          <p className="mt-1 whitespace-pre-wrap text-slate-400 line-clamp-6">
                            {run.result_text || "—"}
                          </p>
                        </div>
                      ))}
                      {log.final_report && (
                        <div className="rounded-lg bg-slate-950/50 p-3 text-sm">
                          <p className="mb-1 font-medium text-slate-300">Relatório final</p>
                          <p className="whitespace-pre-wrap text-slate-400 line-clamp-12">
                            {log.final_report}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              ))
            )}
          </div>
        )}
      </div>
    </>
  );
}
