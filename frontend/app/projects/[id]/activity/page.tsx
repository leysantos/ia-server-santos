"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import LoadingSpinner from "@/components/LoadingSpinner";
import BudgetTracePanel from "@/components/BudgetTracePanel";
import ShellHeader from "@/components/ShellHeader";
import { api } from "@/services/api";
import type {
  ActivityEventItem,
  BudgetSummary,
  DecisionItem,
  ProjectDetail,
} from "@/types/api";
import { cn, formatDate } from "@/lib/utils";

const SOURCE_COLORS: Record<string, string> = {
  chat: "text-blue-300",
  orchestrator: "text-purple-300",
  vision: "text-cyan-300",
  budget: "text-emerald-300",
  upload: "text-amber-300",
  review: "text-orange-300",
};

export default function ProjectActivityPage() {
  const params = useParams();
  const projectId = String(params.id);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [activity, setActivity] = useState<ActivityEventItem[]>([]);
  const [decisions, setDecisions] = useState<DecisionItem[]>([]);
  const [budgets, setBudgets] = useState<BudgetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [proj, act, dec, bud] = await Promise.all([
        api.project(projectId),
        api.projectActivity(projectId),
        api.projectDecisions(projectId),
        api.pricingListSaved(projectId),
      ]);
      setProject(proj);
      setActivity(act.items);
      setDecisions(dec.items);
      setBudgets(bud.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar atividade");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <ShellHeader className="px-6">
        <div className="min-w-0">
          <nav className="mb-1 text-xs text-slate-500">
            <Link href="/projects" className="hover:text-cyan-400">
              Projetos
            </Link>
            <span className="mx-2">/</span>
            <Link href={`/projects/${projectId}`} className="hover:text-cyan-400">
              {project?.name ?? "…"}
            </Link>
            <span className="mx-2">/</span>
            <span className="text-slate-400">Atividade</span>
          </nav>
          <h1 className="text-lg font-semibold text-white">Timeline operacional</h1>
          <p className="text-sm text-slate-500">
            Uploads, análises visuais, orçamentos e decisões técnicas
          </p>
        </div>
      </ShellHeader>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {loading && (
          <div className="flex justify-center py-16">
            <LoadingSpinner label="Carregando timeline..." />
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
            {error}
          </div>
        )}

        {!loading && !error && (
          <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
            <section className="lg:col-span-2 space-y-4">
              <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400">
                Eventos ({activity.length})
              </h2>
              {activity.length === 0 ? (
                <p className="text-sm text-slate-500">
                  Nenhum evento ainda. Faça upload, análise visual ou orçamento vinculado.
                </p>
              ) : (
                <ul className="space-y-3">
                  {activity.map((ev) => (
                    <li
                      key={ev.id}
                      className="rounded-xl bg-slate-900/40 px-4 py-3 ring-1 ring-slate-800/80"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={cn(
                            "text-xs font-medium uppercase",
                            SOURCE_COLORS[ev.source] ?? "text-slate-400"
                          )}
                        >
                          {ev.source}
                        </span>
                        <span className="text-xs text-slate-600">{ev.event_type}</span>
                        {ev.phase && (
                          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                            {ev.phase}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 font-medium text-slate-200">{ev.title}</p>
                      {ev.summary && (
                        <p className="mt-1 text-sm text-slate-400">{ev.summary}</p>
                      )}
                      <p className="mt-2 text-xs text-slate-600">
                        {ev.created_at ? formatDate(ev.created_at) : "—"}
                        {ev.agent_name ? ` · ${ev.agent_name}` : ""}
                        {ev.discipline ? ` · ${ev.discipline}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <aside className="space-y-6">
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                  Decisões ({decisions.length})
                </h2>
                {decisions.length === 0 ? (
                  <p className="text-sm text-slate-500">Nenhuma decisão registrada.</p>
                ) : (
                  <ul className="space-y-2">
                    {decisions.map((d) => (
                      <li
                        key={d.id}
                        className="rounded-lg bg-slate-900/40 px-3 py-2 ring-1 ring-slate-800/80"
                      >
                        <p className="text-sm font-medium text-slate-200">{d.title}</p>
                        {d.description && (
                          <p className="mt-1 text-xs text-slate-400 line-clamp-3">
                            {d.description}
                          </p>
                        )}
                        <p className="mt-1 text-xs text-slate-600">
                          {d.source} · {d.created_at ? formatDate(d.created_at) : "—"}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <BudgetTracePanel projectId={projectId} savedItems={budgets} />

              <div className="flex flex-col gap-2">
                <Link
                  href={`/projects/${projectId}/vision`}
                  className="rounded-lg bg-cyan-500/10 px-3 py-2 text-center text-sm text-cyan-300 ring-1 ring-cyan-500/30 hover:bg-cyan-500/20"
                >
                  Análise visual
                </Link>
                <Link
                  href={`/budget?project=${projectId}`}
                  className="rounded-lg bg-emerald-500/10 px-3 py-2 text-center text-sm text-emerald-300 ring-1 ring-emerald-500/30 hover:bg-emerald-500/20"
                >
                  Orçamento do projeto
                </Link>
              </div>
            </aside>
          </div>
        )}
      </div>
    </>
  );
}
