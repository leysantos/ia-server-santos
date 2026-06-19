"use client";

import type { BudgetSummary } from "@/types/api";
import { cn } from "@/lib/utils";

interface BudgetSavedPanelProps {
  items: BudgetSummary[];
  activeId?: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
}

function fmt(n: number) {
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function BudgetSavedPanel({
  items,
  activeId,
  onOpen,
  onDelete,
  onNew,
}: BudgetSavedPanelProps) {
  return (
    <section className="rounded-xl bg-slate-800/30 ring-1 ring-slate-700/50">
      <div className="flex items-center justify-between border-b border-slate-700/50 px-4 py-2.5">
        <h3 className="text-xs font-medium uppercase tracking-wider text-slate-400">
          Orçamentos salvos
        </h3>
        <button
          type="button"
          onClick={onNew}
          className="rounded bg-cyan-600/20 px-2 py-1 text-xs text-cyan-300 hover:bg-cyan-600/30"
        >
          + Novo
        </button>
      </div>
      {items.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-slate-500">
          Nenhum orçamento salvo. Gere e clique em Salvar.
        </p>
      ) : (
        <ul className="max-h-48 divide-y divide-slate-800/60 overflow-y-auto">
          {items.map((item) => (
            <li
              key={item.id}
              className={cn(
                "flex items-center gap-2 px-4 py-2 hover:bg-slate-800/30",
                activeId === item.id && "bg-violet-500/10"
              )}
            >
              <button
                type="button"
                onClick={() => onOpen(item.id)}
                className="min-w-0 flex-1 text-left"
              >
                <p className="truncate text-sm text-slate-200">{item.title}</p>
                <p className="text-xs text-slate-500">
                  R$ {fmt(item.grand_total)} · {item.obra_type} ·{" "}
                  {item.updated_at ? new Date(item.updated_at).toLocaleDateString("pt-BR") : ""}
                </p>
              </button>
              <button
                type="button"
                onClick={() => onDelete(item.id)}
                className="shrink-0 rounded px-2 py-1 text-xs text-red-400 hover:bg-red-500/10"
                title="Excluir"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
