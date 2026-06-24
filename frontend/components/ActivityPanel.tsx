"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { useActivity } from "@/context/ActivityContext";

const SOURCE_LABELS: Record<string, string> = {
  chat: "Chat",
  orchestrator: "Orquestrador",
  vision: "Visão",
  budget: "Orçamento",
  upload: "Upload",
  review: "Revisão",
  system: "Sistema",
};

const STATUS_DOT: Record<string, string> = {
  running: "bg-brand-400 animate-pulse",
  done: "bg-emerald-400",
  error: "bg-red-400",
};

export default function ActivityPanel() {
  const { entries, open, setOpen, clearActivity } = useActivity();

  if (!open) {
    const running = entries.filter((e) => e.status === "running").length;
    if (running === 0 && entries.length === 0) return null;
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 flex items-center gap-2 rounded-full border border-white/5 bg-surface-card px-4 py-2 text-sm text-slate-200 shadow-lg backdrop-blur"
      >
        {running > 0 && <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulse" />}
        Atividade ({entries.length})
      </button>
    );
  }

  return (
    <aside className="flex h-full w-80 shrink-0 flex-col border-l border-white/5 bg-surface/95 backdrop-blur-xl">
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Atividade</h2>
          <p className="text-xs text-slate-500">Pipelines em tempo real</p>
        </div>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={clearActivity}
            className="rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-800 hover:text-slate-300"
          >
            Limpar
          </button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-800 hover:text-slate-300"
          >
            Fechar
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {entries.length === 0 ? (
          <p className="px-2 py-8 text-center text-sm text-slate-500">
            Nenhuma atividade recente. Use chat, orçamento ou análise visual.
          </p>
        ) : (
          <ul className="space-y-2">
            {entries.map((entry) => (
              <li
                key={entry.id}
                className="rounded-lg border border-white/5 bg-surface-card px-3 py-2"
              >
                <div className="mb-1 flex items-center gap-2">
                  <span className={cn("h-2 w-2 shrink-0 rounded-full", STATUS_DOT[entry.status])} />
                  <span className="text-xs font-medium text-brand-300/90">
                    {SOURCE_LABELS[entry.source] ?? entry.source}
                  </span>
                  {entry.phase && (
                    <span className="truncate text-xs text-slate-500">{entry.phase}</span>
                  )}
                </div>
                <p className="text-sm text-slate-200">{entry.message}</p>
                {(entry.agent || entry.discipline) && (
                  <p className="mt-1 text-xs text-slate-500">
                    {[entry.discipline, entry.agent].filter(Boolean).join(" · ")}
                  </p>
                )}
                {entry.projectId && (
                  <Link
                    href={`/projects/${entry.projectId}/activity`}
                    className="mt-1 inline-block text-xs text-brand-500 hover:text-brand-400"
                  >
                    Ver timeline do projeto
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-white/5 px-4 py-2">
        <Link
          href="/console"
          className="text-xs text-slate-500 hover:text-brand-400"
        >
          Abrir Orchestrator Console →
        </Link>
      </div>
    </aside>
  );
}
