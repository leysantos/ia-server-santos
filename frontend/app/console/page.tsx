"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import LoadingSpinner from "@/components/LoadingSpinner";
import PipelineSteps, { type PipelineStep } from "@/components/PipelineSteps";
import ShellHeader from "@/components/ShellHeader";
import { useActionDialog } from "@/hooks/useActionDialog";
import { api } from "@/services/api";
import type {
  ConsoleLiveResponse,
  ConsoleLogItem,
  ConsoleStatsResponse,
  OllamaQueueItem,
  OpsLogItem,
  RuntimeJobItem,
  VramSnapshot,
} from "@/types/api";
import { cn, formatDate } from "@/lib/utils";

const POLL_FALLBACK_MS = 5000;

const KIND_LABELS: Record<string, string> = {
  vision: "Visão",
  chat: "Chat",
  budget: "Orçamento",
  orchestrator: "Orquestrador",
  norm_bulk: "Importação NBR",
  knowledge: "Indexação FAISS",
  maintenance: "Manutenção / Backup",
};

const QUEUE_STATE_LABELS: Record<string, string> = {
  on_gpu: "Na GPU",
  running: "Executando",
  queued: "Na fila",
};

const QUEUE_STATE_COLORS: Record<string, string> = {
  on_gpu: "bg-emerald-500",
  running: "bg-cyan-500",
  queued: "bg-amber-500/80",
};

const MODEL_VRAM_COLORS = [
  "bg-cyan-500/70",
  "bg-emerald-500/65",
  "bg-violet-500/60",
  "bg-amber-500/55",
  "bg-slate-400/50",
];

function formatVramMb(mb: number | null | undefined): string {
  if (mb == null) return "—";
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${Math.round(mb)} MB`;
}

function VramVisualizer({ vram }: { vram: VramSnapshot | null | undefined }) {
  if (!vram?.available || !vram.total_mb) {
    return (
      <p className="text-sm text-slate-500">
        VRAM indisponível —{" "}
        <span className="text-slate-600">requer nvidia-smi no servidor</span>
      </p>
    );
  }

  const total = vram.total_mb;
  const usedPct = vram.memory_percent ?? 0;
  const isTight = usedPct >= 90;

  type Segment = { key: string; label: string; mb: number; color: string };

  const segments: Segment[] = vram.models.map((model, index) => ({
    key: model.name,
    label: model.name.split(":")[0],
    mb: model.size_vram_mb,
    color: MODEL_VRAM_COLORS[index % MODEL_VRAM_COLORS.length],
  }));

  if (vram.other_mb && vram.other_mb > 0) {
    segments.push({
      key: "other",
      label: "sistema",
      mb: vram.other_mb,
      color: "bg-slate-500/45",
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <p
          className={cn(
            "text-sm font-medium tabular-nums text-slate-200",
            isTight && "text-amber-300"
          )}
        >
          {formatVramMb(vram.used_mb)}
          <span className="font-normal text-slate-500"> / </span>
          {formatVramMb(vram.total_mb)}
          <span className="ml-2 text-xs font-normal text-slate-500">
            {usedPct.toFixed(0)}% ocupada
          </span>
        </p>
        <div className="flex gap-4 text-xs text-slate-500">
          <span>
            Ollama{" "}
            <span className="font-medium text-cyan-400/90">
              {formatVramMb(vram.ollama_allocated_mb)}
            </span>
          </span>
          <span>
            Livre{" "}
            <span className="font-medium text-slate-300">{formatVramMb(vram.free_mb)}</span>
          </span>
          {vram.utilization_percent != null && (
            <span className="hidden sm:inline">
              Compute{" "}
              <span className="font-medium text-slate-300">
                {vram.utilization_percent.toFixed(0)}%
              </span>
            </span>
          )}
        </div>
      </div>

      <div className="flex h-2.5 overflow-hidden rounded-md bg-slate-800/80 ring-1 ring-slate-700/50">
        {segments.map((seg) => {
          const pct = total > 0 ? (seg.mb / total) * 100 : 0;
          if (pct <= 0.3) return null;
          return (
            <div
              key={seg.key}
              className={cn(
                "border-r border-slate-900/30 transition-all duration-500 last:border-r-0",
                seg.color
              )}
              style={{ width: `${pct}%` }}
              title={`${seg.label}: ${formatVramMb(seg.mb)} (${pct.toFixed(0)}%)`}
            />
          );
        })}
      </div>

      {segments.length > 0 && (
        <ul className="flex flex-wrap gap-x-3 gap-y-1.5 text-xs">
          {segments.map((seg) => {
            const pct = total > 0 ? (seg.mb / total) * 100 : 0;
            return (
              <li key={seg.key} className="flex items-center gap-1.5 text-slate-400">
                <span className={cn("h-2 w-2 shrink-0 rounded-sm", seg.color)} />
                <span className="text-slate-300">{seg.label}</span>
                <span className="tabular-nums text-slate-500">
                  {formatVramMb(seg.mb)}
                  <span className="text-slate-600"> ({pct.toFixed(0)}%)</span>
                </span>
              </li>
            );
          })}
          {vram.free_mb != null && vram.free_mb > 0 && (
            <li className="flex items-center gap-1.5 text-slate-500">
              <span className="h-2 w-2 shrink-0 rounded-sm bg-slate-800 ring-1 ring-slate-700" />
              livre {formatVramMb(vram.free_mb)}
            </li>
          )}
        </ul>
      )}

      {isTight && (
        <p className="text-xs text-amber-400/80">
          VRAM no limite — considere descarregar modelos ou usar análise rápida.
        </p>
      )}
    </div>
  );
}

function OllamaQueueBar({ queue }: { queue: ConsoleLiveResponse["ollama_queue"] }) {
  if (!queue || queue.depth === 0) {
    return (
      <p className="text-sm text-slate-500">
        Fila Ollama vazia — nenhum job competindo pela GPU.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3 text-xs text-slate-400">
        <span>{queue.depth} job(s) ativo(s)</span>
        <span className="text-emerald-400">{queue.on_gpu_count} na GPU</span>
        <span className="text-amber-300">{queue.waiting_count} aguardando</span>
        <span>{queue.loaded_slots} modelo(s) em VRAM</span>
      </div>
      <div className="flex h-3 overflow-hidden rounded-full bg-slate-800 ring-1 ring-slate-700/80">
        {queue.items.map((item: OllamaQueueItem) => (
          <div
            key={item.job_id}
            className={cn(
              "min-w-[8%] flex-1 border-r border-slate-900/60 last:border-r-0 transition-all",
              QUEUE_STATE_COLORS[item.state] ?? "bg-slate-600"
            )}
            title={`${KIND_LABELS[item.kind] ?? item.kind}: ${item.label}`}
          />
        ))}
      </div>
      <ul className="space-y-1.5">
        {queue.items.map((item) => (
          <li
            key={item.job_id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-950/50 px-3 py-2 text-xs"
          >
            <span className="text-slate-300">
              <span className="font-medium text-slate-500">#{item.position}</span>{" "}
              {KIND_LABELS[item.kind] ?? item.kind} · {item.label}
            </span>
            <span
              className={cn(
                item.state === "on_gpu" && "text-emerald-400",
                item.state === "running" && "text-cyan-400",
                item.state === "queued" && "text-amber-300"
              )}
            >
              {QUEUE_STATE_LABELS[item.state] ?? item.state}
              {item.model ? ` · ${item.model}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const LOG_LEVEL_COLORS: Record<string, string> = {
  info: "text-slate-300",
  warn: "text-amber-300",
  error: "text-red-300",
};

function formatLogTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function OpsLiveLog({ logs }: { logs: OpsLogItem[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(0);

  useEffect(() => {
    if (logs.length > prevCountRef.current && containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
    prevCountRef.current = logs.length;
  }, [logs]);

  if (logs.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Aguardando atividade — inicie chat, visão, orçamento, importação NBR ou orquestração.
      </p>
    );
  }

  return (
    <div
      ref={containerRef}
      className="max-h-72 overflow-y-auto rounded-xl bg-slate-950/90 p-3 font-mono text-xs ring-1 ring-slate-800/80"
    >
      {logs.map((log) => (
        <div
          key={log.id}
          className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-b border-slate-900/60 py-1.5 last:border-0"
        >
          <span className="shrink-0 text-slate-600">{formatLogTime(log.ts)}</span>
          <span className="shrink-0 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase text-cyan-400">
            {KIND_LABELS[log.source] ?? log.source}
          </span>
          {log.phase && (
            <span className="shrink-0 text-[10px] uppercase text-slate-500">{log.phase}</span>
          )}
          <span className={cn("min-w-0 flex-1", LOG_LEVEL_COLORS[log.level] ?? "text-slate-300")}>
            {log.message}
          </span>
        </div>
      ))}
    </div>
  );
}

function jobSteps(job: RuntimeJobItem): PipelineStep[] {
  if (job.status !== "running") {
    return [{ id: "done", label: job.status, status: job.status === "completed" ? "done" : "error" }];
  }
  return [
    { id: "phase", label: job.phase ?? "processando", status: "running", detail: job.message ?? undefined },
    {
      id: "progress",
      label: job.percent != null ? `${job.percent}%` : "…",
      status: "running",
    },
  ];
}

export default function ConsolePage() {
  const [live, setLive] = useState<ConsoleLiveResponse | null>(null);
  const [logs, setLogs] = useState<ConsoleLogItem[]>([]);
  const [stats, setStats] = useState<ConsoleStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [liveMode, setLiveMode] = useState<"sse" | "poll">("sse");
  const { confirm, ActionDialogHost } = useActionDialog();

  const loadLive = useCallback(async () => {
    try {
      setLive(await api.consoleLive());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar console live");
    }
  }, []);

  const loadStatic = useCallback(async () => {
    const [logsRes, statsRes] = await Promise.all([
      api.consoleLogs(30),
      api.consoleStats(),
    ]);
    setLogs(logsRes.items);
    setStats(statsRes);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      await Promise.all([loadLive(), loadStatic()]);
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadLive, loadStatic]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    (async () => {
      try {
        for await (const snapshot of api.consoleLiveStream(controller.signal)) {
          if (cancelled) break;
          setLive(snapshot);
          setLiveMode("sse");
          setError(null);
        }
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        setLiveMode("poll");
        setError(
          err instanceof Error
            ? `SSE indisponível (${err.message}) — usando polling`
            : "SSE indisponível — usando polling"
        );
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (liveMode !== "poll") return;
    const id = setInterval(loadLive, POLL_FALLBACK_MS);
    return () => clearInterval(id);
  }, [liveMode, loadLive]);

  const handleUnloadModel = async (model: string) => {
    const ok = await confirm({
      title: "Descarregar modelo",
      message: `Descarregar «${model}» da GPU? Inferências em curso neste modelo serão interrompidas.`,
      confirmLabel: "Descarregar",
      destructive: true,
    });
    if (!ok) return;
    setBusy(model);
    try {
      const res = await api.consoleUnloadModel(model);
      setActionMsg(res.ok ? `Modelo ${model} descarregado.` : res.error ?? "Falha ao descarregar");
      await loadLive();
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Erro");
    } finally {
      setBusy(null);
    }
  };

  const handleUnloadAll = async () => {
    const ok = await confirm({
      title: "Descarregar todos os modelos",
      message:
        "Libera a GPU descarregando todos os modelos Ollama residentes. Jobs em andamento podem falhar.",
      confirmLabel: "Descarregar todos",
      destructive: true,
    });
    if (!ok) return;
    setBusy("__all__");
    try {
      const res = await api.consoleUnloadAllModels();
      setActionMsg(
        res.ok
          ? `Descarregados: ${(res.unloaded ?? []).join(", ") || "nenhum"}`
          : res.error ?? "Falha parcial — veja detalhes"
      );
      await loadLive();
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Erro");
    } finally {
      setBusy(null);
    }
  };

  const handleCancelJob = async (job: RuntimeJobItem) => {
    const ok = await confirm({
      title: "Cancelar job",
      message: `Cancelar «${job.label}»? A interrupção ocorre entre arquivos (não no meio de um modelo).`,
      confirmLabel: "Cancelar job",
      destructive: true,
    });
    if (!ok) return;
    setBusy(job.id);
    try {
      await api.consoleCancelJob(job.id);
      setActionMsg(`Cancelamento solicitado para ${job.label}`);
      await loadLive();
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Erro");
    } finally {
      setBusy(null);
    }
  };

  const pipelineForLog = (log: ConsoleLogItem): PipelineStep[] => {
    const steps: PipelineStep[] = [{ id: "decompose", label: "Decomposição", status: "done" }];
    for (const d of log.disciplines) {
      const run = log.agent_runs.find((r) => r.discipline === d);
      steps.push({
        id: `agent-${d}`,
        label: d,
        status: run ? "done" : "pending",
        detail: run?.agent_name ?? undefined,
      });
    }
    steps.push({ id: "synthesis", label: "Síntese", status: log.final_report ? "done" : "pending" });
    return steps;
  };

  const gpu = live?.gpu as { percent?: number; memory_percent?: number; available?: boolean } | undefined;

  return (
    <>
      <ShellHeader className="px-6" showModelsStatus>
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold text-white">Operations Console</h1>
          <p className="text-sm text-slate-500">
            Tempo real · GPU · modelos Ollama · jobs ativos · histórico
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-emerald-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
            {liveMode === "sse" ? "SSE live" : `Poll ${POLL_FALLBACK_MS / 1000}s`}
          </span>
          {live && live.loaded_model_count > 0 && (
            <button
              type="button"
              disabled={busy === "__all__"}
              onClick={handleUnloadAll}
              className="rounded-lg bg-red-600/20 px-3 py-1.5 text-xs font-medium text-red-300 ring-1 ring-red-500/40 hover:bg-red-600/30 disabled:opacity-50"
            >
              Parar todos (GPU)
            </button>
          )}
        </div>
      </ShellHeader>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {actionMsg && (
          <div className="mb-4 rounded-xl bg-cyan-500/10 px-4 py-3 text-sm text-cyan-200 ring-1 ring-cyan-500/30">
            {actionMsg}
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
            {error}
          </div>
        )}

        {loading && !live ? (
          <div className="flex justify-center py-16">
            <LoadingSpinner label="Conectando ao console..." />
          </div>
        ) : (
          <div className="mx-auto max-w-6xl space-y-8">
            {/* Live metrics */}
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Sistema agora
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  {
                    label: "GPU",
                    value: gpu?.available ? `${gpu.percent ?? gpu.memory_percent ?? 0}%` : "—",
                  },
                  { label: "CPU", value: live?.cpu_percent != null ? `${live.cpu_percent}%` : "—" },
                  {
                    label: "RAM",
                    value: live?.memory_percent != null ? `${live.memory_percent}%` : "—",
                  },
                  {
                    label: "VRAM",
                    value:
                      live?.vram?.available && live.vram.memory_percent != null
                        ? `${live.vram.memory_percent.toFixed(0)}%`
                        : "—",
                  },
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
              <div className="mt-3 rounded-xl bg-slate-900/50 px-4 py-3 ring-1 ring-slate-800/80">
                <p className="mb-2.5 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Memória GPU
                </p>
                <VramVisualizer vram={live?.vram} />
              </div>
              {!live?.ollama_reachable && (
                <p className="mt-2 text-sm text-amber-300">
                  Ollama indisponível — {live?.ollama_error ?? "verifique ollama serve"}
                </p>
              )}
            </section>

            {/* Live ops log */}
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Log ao vivo
              </h2>
              <OpsLiveLog logs={live?.ops_logs ?? []} />
            </section>

            {/* Ollama queue */}
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Fila Ollama
              </h2>
              <OllamaQueueBar queue={live?.ollama_queue} />
            </section>

            {/* Ollama models in VRAM */}
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Modelos em uso (VRAM)
              </h2>
              {live?.loaded_models.length === 0 ? (
                <p className="text-sm text-slate-500">Nenhum modelo carregado na GPU no momento.</p>
              ) : (
                <ul className="space-y-2">
                  {live?.loaded_models.map((m) => (
                    <li
                      key={m.name}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-900/40 px-4 py-3 ring-1 ring-slate-800/80"
                    >
                      <div>
                        <p className="font-medium text-cyan-300">{m.name}</p>
                        <p className="text-xs text-slate-500">
                          VRAM ~{m.size_vram_mb} MB
                          {m.context_length ? ` · ctx ${m.context_length}` : ""}
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={busy === m.name}
                        onClick={() => handleUnloadModel(m.name)}
                        className="rounded-lg bg-red-600/15 px-3 py-1.5 text-xs text-red-300 ring-1 ring-red-500/30 hover:bg-red-600/25 disabled:opacity-50"
                      >
                        Parar modelo
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Active jobs */}
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Jobs em processamento ({live?.active_job_count ?? 0})
              </h2>
              {live?.active_jobs.length === 0 ? (
                <p className="text-sm text-slate-500">Nenhum job longo ativo no servidor.</p>
              ) : (
                <ul className="space-y-3">
                  {live?.active_jobs.map((job) => (
                    <li
                      key={job.id}
                      className="rounded-xl bg-slate-900/40 p-4 ring-1 ring-emerald-500/20"
                    >
                      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium text-white">
                            <span className="text-emerald-400">
                              {KIND_LABELS[job.kind] ?? job.kind}
                            </span>
                            {" · "}
                            {job.label}
                          </p>
                          <p className="text-xs text-slate-500">
                            {job.model ? `Modelo: ${job.model} · ` : ""}
                            {job.elapsed_sec != null ? `${job.elapsed_sec}s · ` : ""}
                            {job.message ?? job.phase ?? "—"}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          {job.project_id && (
                            <Link
                              href={`/projects/${job.project_id}/vision`}
                              className="text-xs text-cyan-500 hover:text-cyan-400"
                            >
                              Abrir
                            </Link>
                          )}
                          <button
                            type="button"
                            disabled={busy === job.id || job.cancel_requested}
                            onClick={() => handleCancelJob(job)}
                            className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50"
                          >
                            {job.cancel_requested ? "Cancelando…" : "Cancelar"}
                          </button>
                        </div>
                      </div>
                      <PipelineSteps steps={jobSteps(job)} />
                      {job.percent != null && (
                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
                          <div
                            className="h-full bg-emerald-500 transition-all duration-500"
                            style={{ width: `${job.percent}%` }}
                          />
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Recent completed jobs */}
            {(live?.recent_jobs.filter((j) => j.status !== "running").length ?? 0) > 0 && (
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                  Jobs recentes
                </h2>
                <ul className="space-y-1">
                  {live?.recent_jobs
                    .filter((j) => j.status !== "running")
                    .slice(0, 8)
                    .map((job) => (
                      <li
                        key={job.id}
                        className="flex justify-between rounded-lg bg-slate-950/40 px-3 py-2 text-xs"
                      >
                        <span className="text-slate-400">
                          {KIND_LABELS[job.kind] ?? job.kind} · {job.label}
                        </span>
                        <span
                          className={cn(
                            job.status === "completed" && "text-emerald-400",
                            job.status === "cancelled" && "text-amber-400",
                            job.status === "error" && "text-red-400"
                          )}
                        >
                          {job.status}
                        </span>
                      </li>
                    ))}
                </ul>
              </section>
            )}

            {/* Historical orchestrator logs */}
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Histórico de orquestrações
                {stats ? ` (${stats.orchestrator_logs} total)` : ""}
              </h2>
              {logs.length === 0 ? (
                <p className="text-sm text-slate-500">
                  Nenhuma orquestração registrada.{" "}
                  <Link href="/orchestrate" className="text-cyan-400 hover:underline">
                    /orchestrate
                  </Link>
                </p>
              ) : (
                <div className="space-y-4">
                  {logs.map((log) => (
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
                            {log.agent_count} agente(s)
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
                        {expanded === log.id ? "Ocultar" : "Detalhes"}
                      </button>
                      {expanded === log.id && (
                        <div className="mt-3 space-y-2 border-t border-slate-800/80 pt-3">
                          {log.agent_runs.map((run) => (
                            <div key={run.id} className="rounded-lg bg-slate-950/50 p-3 text-sm">
                              <p className="font-medium text-cyan-300">
                                {run.discipline} · {run.agent_name}
                              </p>
                              <p className="mt-1 line-clamp-4 text-slate-400">
                                {run.result_text || "—"}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
      <ActionDialogHost />
    </>
  );
}
