"use client";

import Link from "next/link";
import type { BudgetSummary } from "@/types/api";
import { cn } from "@/lib/utils";

interface BudgetTracePanelProps {
  projectId?: string | null;
  savedItems: BudgetSummary[];
  className?: string;
}

export default function BudgetTracePanel({
  projectId,
  savedItems,
  className,
}: BudgetTracePanelProps) {
  const linked = projectId
    ? savedItems.filter((b) => b.project_id === projectId)
    : savedItems.slice(0, 5);

  return (
    <section
      className={cn(
        "rounded-xl bg-slate-900/40 p-4 ring-1 ring-slate-800/80",
        className
      )}
    >
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-white">Histórico de orçamentos</h3>
          <p className="text-xs text-slate-500">
            {projectId ? "Versões salvas deste projeto" : "Últimos orçamentos salvos"}
          </p>
        </div>
        {projectId && (
          <Link
            href={`/projects/${projectId}/activity`}
            className="text-xs text-cyan-500 hover:text-cyan-400"
          >
            Timeline
          </Link>
        )}
      </div>

      {linked.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum orçamento salvo ainda.</p>
      ) : (
        <ul className="space-y-2">
          {linked.map((item) => (
            <li
              key={item.id}
              className="flex items-center justify-between rounded-lg bg-slate-950/50 px-3 py-2 text-sm"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-slate-200">{item.title}</p>
                <p className="text-xs text-slate-500">
                  {item.obra_type} · {item.updated_at ? new Date(item.updated_at).toLocaleString("pt-BR") : "—"}
                </p>
              </div>
              <span className="shrink-0 text-sm font-medium text-emerald-400">
                R$ {item.grand_total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
