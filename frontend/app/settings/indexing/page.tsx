"use client";

import Link from "next/link";
import { useState } from "react";
import { useSettingsKnowledge } from "@/contexts/SettingsKnowledgeContext";
import { cn } from "@/lib/utils";

const BASE_COLORS: Record<string, string> = {
  nbr: "from-blue-500/20 to-blue-600/10 ring-blue-500/30 text-blue-300",
  sinapi: "from-emerald-500/20 to-emerald-600/10 ring-emerald-500/30 text-emerald-300",
  tcpo: "from-amber-500/20 to-amber-600/10 ring-amber-500/30 text-amber-300",
};

function CoverageBanner() {
  const { stats } = useSettingsKnowledge();
  const cov = stats?.nbr_coverage;
  if (!cov || cov.files_on_disk === 0) return null;

  const pct = cov.effective_file_coverage_pct ?? cov.file_coverage_pct ?? cov.coverage_pct;
  const low = pct < 95;
  return (
    <div
      className={cn(
        "mb-6 rounded-xl p-4 ring-1",
        low
          ? "bg-amber-500/10 ring-amber-500/40"
          : "bg-emerald-500/10 ring-emerald-500/40",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className={cn("text-sm font-semibold", low ? "text-amber-200" : "text-emerald-200")}>
            Cobertura FAISS — base NBR
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            {cov.effective_indexed_files ?? cov.indexed_files} de {cov.files_on_disk} PDFs com
            conteúdo indexado (
            <strong className={low ? "text-amber-300" : "text-emerald-300"}>
              {pct}%
            </strong>
            ) · {cov.faiss_chunks.toLocaleString()} chunks · códigos {cov.code_coverage_pct ?? 0}%
            {(cov.dedup_only_files ?? 0) > 0 && (
              <span className="text-slate-500">
                {" "}
                · {cov.dedup_only_files} via dedup (mesmo código, outro path)
              </span>
            )}
          </p>
          {cov.files_missing_disk > 0 && (
            <p className="mt-1 text-xs text-red-300">
              {cov.files_missing_disk} entrada(s) no catálogo sem arquivo no disco
            </p>
          )}
          {low && cov.sample_not_indexed.length > 0 && (
            <p className="mt-2 text-xs text-slate-500">
              PDFs pendentes (amostra): {cov.sample_not_indexed.slice(0, 8).join(", ")}
              {cov.sample_not_indexed.length > 8 ? "…" : ""}
            </p>
          )}
        </div>
        <div className="text-right">
          <div
            className={cn(
              "text-3xl font-bold tabular-nums",
              low ? "text-amber-300" : "text-emerald-300",
            )}
          >
            {pct}%
          </div>
        </div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className={cn("h-full transition-all", low ? "bg-amber-500" : "bg-emerald-500")}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}

function IndexProgressPanel() {
  const { indexing, indexProgress } = useSettingsKnowledge();
  if (!indexing || !indexProgress) return null;

  const pct = indexProgress.percent ?? 0;
  const current = indexProgress.current ?? 0;
  const total = indexProgress.total ?? 0;

  return (
    <div className="mb-6 rounded-xl bg-cyan-500/10 p-4 ring-1 ring-cyan-500/30">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-cyan-200">
          Indexando {indexing === "all" ? "todas as bases" : indexing.toUpperCase()}…
        </p>
        <Link href="/console" className="text-xs text-cyan-400 hover:underline">
          Abrir Console →
        </Link>
      </div>
      <p className="mt-1 text-xs text-slate-400">
        {indexProgress.message ?? "Processando…"}
        {total > 0 && ` (${current}/${total})`}
      </p>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full bg-cyan-500 transition-all duration-500"
          style={{ width: `${Math.max(pct, total > 0 ? 2 : 0)}%` }}
        />
      </div>
    </div>
  );
}

export default function SettingsIndexingPage() {
  const { options, stats, handleIndex, indexing, indexProgress } = useSettingsKnowledge();
  const [indexResult, setIndexResult] = useState<string | null>(null);
  const [indexError, setIndexError] = useState<string | null>(null);
  const [forceReindex, setForceReindex] = useState(false);

  if (!options) return null;

  const indexChunks = stats?.index?.multi_index ?? {};
  const cov = stats?.nbr_coverage;
  const nbrLow = (cov?.file_coverage_pct ?? cov?.coverage_pct ?? 100) < 95;

  const runIndex = async (base?: string) => {
    setIndexResult(null);
    setIndexError(null);
    try {
      const msg = await handleIndex(base, forceReindex);
      setIndexResult(msg);
    } catch (err) {
      setIndexError(err instanceof Error ? err.message : "Erro na indexação");
    }
  };

  return (
    <div className="space-y-2">
      <CoverageBanner />
      <IndexProgressPanel />

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <p className="mb-4 text-sm text-slate-500">
          Indexação FAISS para RAG. Jobs longos aparecem no{" "}
          <Link href="/console" className="text-cyan-400 hover:underline">
            Console
          </Link>
          . Com <strong className="text-slate-400">force</strong>, PDFs já indexados são
          reprocessados.
        </p>

        <label className="mb-4 flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={forceReindex}
            onChange={(e) => setForceReindex(e.target.checked)}
            disabled={indexing !== null}
          />
          Forçar reindexação (reprocessar PDFs já no índice)
        </label>

        {nbrLow && indexing !== "nbr" && (
          <button
            type="button"
            disabled={indexing !== null}
            onClick={() => runIndex("nbr")}
            className="mb-4 w-full rounded-lg bg-amber-500/20 px-4 py-3 text-sm font-medium text-amber-200 ring-1 ring-amber-500/40 hover:bg-amber-500/30 disabled:opacity-50 sm:w-auto"
          >
            Completar indexação NBR ({cov?.not_indexed_files ?? "?"} PDFs pendentes)
          </button>
        )}

        <div className="flex flex-wrap gap-2">
          {(options.bases ?? []).map((base) => (
            <button
              key={base.value}
              type="button"
              disabled={indexing !== null}
              onClick={() => runIndex(base.value)}
              className={cn(
                "rounded-lg px-4 py-2 text-sm font-medium ring-1 transition disabled:opacity-50",
                BASE_COLORS[base.value] ?? "bg-slate-800 text-slate-300 ring-slate-700",
                base.value === "nbr" && nbrLow && "ring-amber-500/50",
              )}
            >
              {indexing === base.value
                ? "Indexando…"
                : `${base.label} (${indexChunks[base.value] ?? 0} chunks)`}
            </button>
          ))}
          <button
            type="button"
            disabled={indexing !== null}
            onClick={() => runIndex()}
            className="rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-300 ring-1 ring-cyan-500/40 disabled:opacity-50"
          >
            {indexing === "all" ? "Indexando tudo…" : "Indexar tudo"}
          </button>
        </div>

        {indexResult && <p className="mt-3 text-sm text-emerald-400">{indexResult}</p>}
        {indexError && <p className="mt-3 text-sm text-red-300">{indexError}</p>}
        {indexing && !indexProgress?.message && (
          <p className="mt-3 text-xs text-slate-500">Aguardando progresso no Console…</p>
        )}
      </section>
    </div>
  );
}
