"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import type { SystemBenchmarkResponse } from "@/types/api";
import { cn } from "@/lib/utils";

const HISTORY_LEN = 36;
const POLL_MS_OK = 2000;
const POLL_MS_ERR_MIN = 5000;
const POLL_MS_ERR_MAX = 60000;

type MetricKey = "cpu" | "memory" | "gpu" | "vram";

interface MetricHistory {
  cpu: number[];
  memory: number[];
  gpu: number[];
  vram: number[];
}

const EMPTY_HISTORY: MetricHistory = { cpu: [], memory: [], gpu: [], vram: [] };

function pushHistory(prev: MetricHistory, key: MetricKey, value: number | null): MetricHistory {
  if (value == null || Number.isNaN(value)) return prev;
  const next = [...prev[key], value].slice(-HISTORY_LEN);
  return { ...prev, [key]: next };
}

function Sparkline({
  values,
  stroke,
  gradientId,
  className,
}: {
  values: number[];
  stroke: string;
  gradientId: string;
  className?: string;
}) {
  const width = 56;
  const height = 20;

  if (values.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        className={cn("shrink-0 opacity-30", className)}
        aria-hidden
      >
        <line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke="#475569" strokeWidth={1} />
      </svg>
    );
  }

  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - (Math.min(100, Math.max(0, v)) / 100) * height;
      return `${x},${y}`;
    })
    .join(" ");

  const last = values[values.length - 1] ?? 0;
  const lastX = width;
  const lastY = height - (Math.min(100, Math.max(0, last)) / 100) * height;

  return (
    <svg width={width} height={height} className={cn("shrink-0", className)} aria-hidden>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.25} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${height} ${points} ${width},${height}`}
        fill={`url(#${gradientId})`}
      />
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points}
      />
      <circle cx={lastX} cy={lastY} r={2} fill={stroke} />
    </svg>
  );
}

function MetricRow({
  label,
  value,
  history,
  stroke,
  gradientId,
  detail,
  unavailable,
}: {
  label: string;
  value: number | null;
  history: number[];
  stroke: string;
  gradientId: string;
  detail?: string;
  unavailable?: boolean;
}) {
  const pct = value ?? 0;

  return (
    <div className="group/metric space-y-1" title={detail}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </span>
        <span className="text-[10px] tabular-nums text-slate-400">
          {unavailable ? "N/D" : value != null ? `${value.toFixed(0)}%` : "—"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800/90 ring-1 ring-slate-700/50">
          <div
            className="h-full rounded-full transition-all duration-700 ease-out"
            style={{
              width: unavailable ? "0%" : `${Math.min(100, pct)}%`,
              background: `linear-gradient(90deg, ${stroke}99, ${stroke})`,
            }}
          />
        </div>
        <Sparkline values={history} stroke={stroke} gradientId={gradientId} />
      </div>
      {detail && (
        <p className="sr-only">{detail}</p>
      )}
    </div>
  );
}

export default function SystemBenchmarkPanel() {
  const [snapshot, setSnapshot] = useState<SystemBenchmarkResponse | null>(null);
  const [history, setHistory] = useState<MetricHistory>(EMPTY_HISTORY);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const failStreakRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<(() => Promise<void>) | null>(null);

  const scheduleNext = useCallback((delayMs: number) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      void pollRef.current?.();
    }, delayMs);
  }, []);

  const poll = useCallback(async () => {
    try {
      const data = await api.systemBenchmark();
      if (!mountedRef.current) return;
      failStreakRef.current = 0;
      setSnapshot(data);
      setError(data.available ? null : data.error ?? "Métricas indisponíveis");
      setHistory((prev) => {
        let next = prev;
        next = pushHistory(next, "cpu", data.cpu?.percent ?? null);
        next = pushHistory(next, "memory", data.memory?.percent ?? null);
        const gpuAvailable = data.gpu?.available ?? data.vram?.available ?? false;
        next = pushHistory(
          next,
          "gpu",
          gpuAvailable ? (data.gpu?.percent ?? null) : null
        );
        next = pushHistory(
          next,
          "vram",
          gpuAvailable
            ? (data.vram?.percent ?? data.gpu?.memory_percent ?? null)
            : null
        );
        return next;
      });
      scheduleNext(POLL_MS_OK);
    } catch (err) {
      if (!mountedRef.current) return;
      failStreakRef.current += 1;
      const streak = failStreakRef.current;
      const backoff = Math.min(
        POLL_MS_ERR_MAX,
        POLL_MS_ERR_MIN * Math.pow(2, Math.min(streak - 1, 4))
      );
      setError(
        streak === 1
          ? err instanceof Error
            ? err.message
            : "Falha ao ler benchmark"
          : `API offline — nova tentativa em ${Math.round(backoff / 1000)}s`
      );
      scheduleNext(backoff);
    }
  }, [scheduleNext]);

  pollRef.current = poll;

  useEffect(() => {
    mountedRef.current = true;
    void poll();
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [poll]);

  const gpuAvailable = snapshot?.gpu?.available ?? snapshot?.vram?.available ?? false;
  const memDetail =
    snapshot?.memory?.used_gb != null && snapshot?.memory?.total_gb != null
      ? `${snapshot.memory.used_gb} / ${snapshot.memory.total_gb} GB`
      : undefined;
  const cpuDetail =
    snapshot?.cpu?.cores != null ? `${snapshot.cpu.cores} núcleos lógicos` : undefined;
  const gpuDetail = gpuAvailable
    ? "Utilização CUDA (nvidia-smi)"
    : "Sem GPU NVIDIA (nvidia-smi)";
  const vramUsed =
    snapshot?.vram?.used_mb ?? snapshot?.gpu?.memory_used_mb ?? null;
  const vramTotal =
    snapshot?.vram?.total_mb ?? snapshot?.gpu?.memory_total_mb ?? null;
  const vramDetail =
    gpuAvailable && vramUsed != null && vramTotal != null
      ? `${vramUsed} / ${vramTotal} MB`
      : gpuAvailable
        ? "VRAM NVIDIA"
        : undefined;

  return (
    <div className="w-full">
      <div className="flex w-full flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Benchmark
          </p>
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              error ? "bg-amber-500/80" : "bg-emerald-500/80 animate-pulse"
            )}
            title={error ?? "Atualizando periodicamente"}
          />
        </div>

        <MetricRow
          label="CPU"
          value={snapshot?.cpu?.percent ?? null}
          history={history.cpu}
          stroke="#22d3ee"
          gradientId="bench-cpu"
          detail={cpuDetail}
          unavailable={!snapshot?.available}
        />
        <MetricRow
          label="RAM"
          value={snapshot?.memory?.percent ?? null}
          history={history.memory}
          stroke="#a78bfa"
          gradientId="bench-ram"
          detail={memDetail}
          unavailable={!snapshot?.available}
        />
        <MetricRow
          label="GPU"
          value={gpuAvailable ? (snapshot?.gpu?.percent ?? null) : null}
          history={history.gpu}
          stroke="#34d399"
          gradientId="bench-gpu"
          detail={gpuDetail}
          unavailable={!gpuAvailable}
        />
        <MetricRow
          label="VRAM"
          value={
            gpuAvailable
              ? (snapshot?.vram?.percent ?? snapshot?.gpu?.memory_percent ?? null)
              : null
          }
          history={history.vram}
          stroke="#fbbf24"
          gradientId="bench-vram"
          detail={vramDetail}
          unavailable={!gpuAvailable}
        />

        {error && (
          <p className="truncate text-[9px] text-amber-500/80" title={error}>
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
