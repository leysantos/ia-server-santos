"use client";

import { useState } from "react";
import { useSettingsKnowledge } from "@/contexts/SettingsKnowledgeContext";
import { cn } from "@/lib/utils";

const BASE_COLORS: Record<string, string> = {
  nbr: "from-blue-500/20 to-blue-600/10 ring-blue-500/30 text-blue-300",
  sinapi: "from-emerald-500/20 to-emerald-600/10 ring-emerald-500/30 text-emerald-300",
  tcpo: "from-amber-500/20 to-amber-600/10 ring-amber-500/30 text-amber-300",
};

export default function SettingsIndexingPage() {
  const { options, stats, handleIndex, indexing } = useSettingsKnowledge();
  const [indexResult, setIndexResult] = useState<string | null>(null);
  const [indexError, setIndexError] = useState<string | null>(null);

  if (!options) return null;

  const indexChunks = stats?.index?.multi_index ?? {};

  const runIndex = async (base?: string) => {
    setIndexResult(null);
    setIndexError(null);
    try {
      const msg = await handleIndex(base);
      setIndexResult(msg);
    } catch (err) {
      setIndexError(err instanceof Error ? err.message : "Erro na indexação");
    }
  };

  return (
    <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
      <p className="mb-4 text-sm text-slate-500">
        Use apenas se a indexação automática falhar ou após alterações manuais no disco.
        Cada base FAISS alimenta agentes e consultas específicas (NBR, SINAPI, TCPO…).
      </p>
      <div className="flex flex-wrap gap-2">
        {(options.bases ?? []).map((base) => (
          <button
            key={base.value}
            type="button"
            disabled={indexing !== null}
            onClick={() => runIndex(base.value)}
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
          onClick={() => runIndex()}
          className="rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-300 ring-1 ring-cyan-500/40 disabled:opacity-50"
        >
          {indexing === "all" ? "Indexando tudo…" : "Indexar tudo"}
        </button>
      </div>
      {indexResult && <p className="mt-3 text-sm text-emerald-400">{indexResult}</p>}
      {indexError && (
        <p className="mt-3 text-sm text-red-300">{indexError}</p>
      )}
    </section>
  );
}
