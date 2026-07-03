"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import MobilePageShell from "@/components/mobile/MobilePageShell";
import { api } from "@/services/api";
import type { ProjectSummary } from "@/types/api";
import { cn, formatDate } from "@/lib/utils";

export default function MobileProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.projects(100);
      setProjects(res.items);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = projects.filter((p) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return [p.name, p.description].filter(Boolean).join(" ").toLowerCase().includes(q);
  });

  return (
    <MobilePageShell
      title="Projetos"
      subtitle="Localize e acesse relatórios"
      trailing={
        <Link
          href="/projects"
          className="shrink-0 rounded-lg px-2 py-1 text-xs text-cyan-400 ring-1 ring-cyan-500/30"
        >
          Desktop
        </Link>
      }
    >
      <div className="mx-auto max-w-lg space-y-4">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar projeto…"
          className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
        />

        {loading ? (
          <p className="text-sm text-slate-500">Carregando…</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhum projeto encontrado.</p>
        ) : (
          <ul className="space-y-2">
            {filtered.map((project) => {
              const open = expandedId === project.id;
              return (
                <li
                  key={project.id}
                  className="overflow-hidden rounded-xl bg-slate-900/60 ring-1 ring-slate-800"
                >
                  <button
                    type="button"
                    onClick={() => setExpandedId(open ? null : project.id)}
                    className="flex w-full items-start gap-3 px-4 py-3 text-left"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white">{project.name}</p>
                      {project.updated_at && (
                        <p className="mt-0.5 text-xs text-slate-500">{formatDate(project.updated_at)}</p>
                      )}
                    </div>
                    <span className={cn("text-slate-500 transition", open && "rotate-180")}>▾</span>
                  </button>
                  {open && (
                    <div className="space-y-2 border-t border-slate-800 px-4 py-3">
                      <Link
                        href={`/chat?project=${project.id}`}
                        className="block rounded-lg bg-slate-800/80 px-3 py-2 text-sm text-slate-200"
                      >
                        Chat do projeto
                      </Link>
                      <Link
                        href={`/mobile/budget?project=${project.id}`}
                        className="block rounded-lg bg-slate-800/80 px-3 py-2 text-sm text-slate-200"
                      >
                        Orçamentos do projeto
                      </Link>
                      <Link
                        href={`/projects/${project.id}/review`}
                        className="block rounded-lg bg-slate-800/80 px-3 py-2 text-sm text-slate-200"
                      >
                        Revisão técnica (PDF)
                      </Link>
                      <Link
                        href={`/projects/${project.id}/workflow`}
                        className="block rounded-lg bg-slate-800/80 px-3 py-2 text-sm text-slate-200"
                      >
                        Workflow / GRD (PDF)
                      </Link>
                      <Link
                        href={`/projects/${project.id}`}
                        className="block text-center text-xs text-cyan-400 hover:underline"
                      >
                        Abrir projeto completo
                      </Link>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </MobilePageShell>
  );
}
