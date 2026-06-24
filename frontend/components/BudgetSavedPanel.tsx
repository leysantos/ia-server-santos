"use client";

import { useMemo, useState } from "react";
import type { BudgetSummary } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetInput } from "@/lib/budget-ui";

interface BudgetSavedPanelProps {
  items: BudgetSummary[];
  activeId?: string | null;
  projectFilterLabel?: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  onClearProjectFilter?: () => void;
  layout?: "sidebar" | "full";
}

function fmt(n: number) {
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function matchesSearch(item: BudgetSummary, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    item.title,
    item.orcamento,
    item.obra_type,
    item.input_text,
    item.grand_total?.toString(),
    item.updated_at ? new Date(item.updated_at).toLocaleDateString("pt-BR") : "",
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
}

export default function BudgetSavedPanel({
  items,
  activeId,
  projectFilterLabel,
  onOpen,
  onDelete,
  onNew,
  onClearProjectFilter,
  layout = "sidebar",
}: BudgetSavedPanelProps) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(
    () => items.filter((item) => matchesSearch(item, search)),
    [items, search]
  );

  return (
    <section className="rounded-xl bg-slate-800/30 ring-1 ring-slate-700/50">
      <div className="flex items-center justify-between border-b border-slate-700/50 px-4 py-2.5">
        <div className="min-w-0">
          <h3 className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Orçamentos salvos
          </h3>
          {projectFilterLabel && (
            <p className="truncate text-[11px] text-cyan-400/90">Projeto: {projectFilterLabel}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onNew}
          className="shrink-0 rounded bg-cyan-600/20 px-2 py-1 text-xs text-cyan-300 hover:bg-cyan-600/30"
        >
          + Novo
        </button>
      </div>

      <div className="border-b border-slate-800/60 px-4 py-2.5">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar por nome, código, tipo ou valor…"
          className={cn(budgetInput, "text-xs")}
          aria-label="Buscar orçamentos salvos"
        />
        {search.trim() && (
          <p className="mt-1.5 text-[11px] text-slate-500">
            {filtered.length} de {items.length} orçamento(s)
          </p>
        )}
      </div>

      {projectFilterLabel && onClearProjectFilter && (
        <div className="border-b border-slate-800/60 px-4 py-2">
          <button
            type="button"
            onClick={onClearProjectFilter}
            className="text-[11px] text-slate-500 hover:text-slate-300"
          >
            Ver todos os orçamentos
          </button>
        </div>
      )}
      {items.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-slate-500">
          {projectFilterLabel
            ? "Nenhum orçamento salvo neste projeto."
            : "Nenhum orçamento salvo. Gere e clique em Salvar."}
        </p>
      ) : filtered.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-slate-500">
          Nenhum orçamento corresponde à busca.
        </p>
      ) : (
        <ul
          className={cn(
            "divide-y divide-slate-800/60 overflow-y-auto",
            layout === "full" ? "max-h-[min(520px,60vh)]" : "max-h-48"
          )}
        >
          {filtered.map((item) => (
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
                {item.orcamento && (
                  <p className="truncate font-mono text-[11px] text-cyan-400/80">{item.orcamento}</p>
                )}
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
