"use client";

import Link from "next/link";
import { useKnowledgeWebImportOptional } from "@/context/KnowledgeWebImportContext";

/** Banner global — importação web (ex. DNIT/SICRO) continua ao navegar entre páginas. */
export default function KnowledgeWebImportBanner() {
  const job = useKnowledgeWebImportOptional();

  if (!job?.importing) {
    return null;
  }

  const pct = job.progress?.percent ?? 0;
  const host = (() => {
    if (!job.pageUrl) return "site";
    try {
      return new URL(job.pageUrl).hostname;
    } catch {
      return job.pageUrl.slice(0, 40);
    }
  })();

  return (
    <div className="border-b border-amber-500/20 bg-amber-950/35 px-4 py-2">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 text-sm">
        <p className="text-amber-100">
          <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-amber-400" />
          Importação de conhecimento em andamento — {host}
          {job.progress?.message ? `: ${job.progress.message}` : ""}
        </p>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-amber-400">{pct}%</span>
          <Link
            href="/settings/imports"
            className="rounded-lg bg-amber-600/25 px-3 py-1 text-xs font-medium text-amber-50 ring-1 ring-amber-500/40 hover:bg-amber-600/40"
          >
            Ver importação
          </Link>
          <Link
            href="/console"
            className="rounded-lg bg-slate-800/80 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-slate-600 hover:bg-slate-700"
          >
            Console
          </Link>
        </div>
      </div>
      <div className="mx-auto mt-1.5 h-1 max-w-6xl overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
