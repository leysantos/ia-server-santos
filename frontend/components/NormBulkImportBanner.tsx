"use client";

import Link from "next/link";
import { useNormBulkImportOptional } from "@/context/NormBulkImportContext";

/** Banner global — importação NBR/NR continua ao navegar entre páginas. */
export default function NormBulkImportBanner() {
  const job = useNormBulkImportOptional();

  if (!job?.importing) {
    return null;
  }

  const pct = job.progress?.percent ?? 0;
  const label = job.folderName
    ? `«${job.folderName}» · ${job.fileCount.toLocaleString("pt-BR")} PDF(s)`
    : `${job.fileCount.toLocaleString("pt-BR")} PDF(s)`;

  return (
    <div className="border-b border-violet-500/20 bg-violet-950/40 px-4 py-2">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 text-sm">
        <p className="text-violet-200">
          <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-violet-400" />
          Importação NBR/NR em andamento — {label}
          {job.progress?.message ? `: ${job.progress.message}` : ""}
        </p>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-violet-400">{pct}%</span>
          <Link
            href="/settings/imports"
            className="rounded-lg bg-violet-600/30 px-3 py-1 text-xs font-medium text-violet-100 ring-1 ring-violet-500/40 hover:bg-violet-600/50"
          >
            Ver importação
          </Link>
        </div>
      </div>
      <div className="mx-auto mt-1.5 h-1 max-w-6xl overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full bg-violet-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
