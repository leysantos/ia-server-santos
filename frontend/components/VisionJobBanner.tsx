"use client";

import Link from "next/link";
import { useVisionJobOptional } from "@/context/VisionJobContext";

/** Banner global — visível em qualquer página enquanto análise visual roda em background. */
export default function VisionJobBanner() {
  const job = useVisionJobOptional();

  if (!job?.analyzing || !job.projectId) {
    return null;
  }

  const pct = job.progress?.percent ?? 0;
  const label = job.projectName ?? "projeto";

  return (
    <div className="border-b border-emerald-500/20 bg-emerald-950/40 px-4 py-2">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 text-sm">
        <p className="text-emerald-200">
          <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
          Análise visual ({job.mode}) em andamento — {label}
          {job.progress?.message ? `: ${job.progress.message}` : ""}
        </p>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-emerald-400">{pct}%</span>
          <Link
            href={`/projects/${job.projectId}/vision`}
            className="rounded-lg bg-emerald-600/30 px-3 py-1 text-xs font-medium text-emerald-100 ring-1 ring-emerald-500/40 hover:bg-emerald-600/50"
          >
            Ver progresso
          </Link>
        </div>
      </div>
      <div className="mx-auto mt-1.5 h-1 max-w-6xl overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
