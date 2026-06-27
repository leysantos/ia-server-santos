"use client";

import { useMemo, useState } from "react";
import type { BudgetSummary } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetInput } from "@/lib/budget-ui";

interface BudgetSavedPanelProps {
  items: BudgetSummary[];
  selectedId?: string | null;
  activeId?: string | null;
  projectFilterLabel?: string | null;
  onSelect: (id: string) => void;
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

function IconPencil({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
      />
    </svg>
  );
}

function IconTrash({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  );
}

export default function BudgetSavedPanel({
  items,
  selectedId,
  activeId,
  projectFilterLabel,
  onSelect,
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
          {filtered.map((item) => {
            const isSelected = selectedId === item.id;
            const isActive = activeId === item.id;
            return (
              <li
                key={item.id}
                className={cn(
                  "flex items-center gap-2 px-3 py-2.5",
                  isSelected && "bg-violet-500/10 ring-1 ring-inset ring-violet-500/25",
                  !isSelected && "hover:bg-slate-800/30"
                )}
              >
                <button
                  type="button"
                  onClick={() => onSelect(item.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <p className="truncate text-sm font-medium text-slate-200">{item.title}</p>
                  {item.orcamento && (
                    <p className="truncate font-mono text-[11px] text-cyan-400/80">{item.orcamento}</p>
                  )}
                  <p className="text-xs text-slate-500">
                    {item.obra_type} ·{" "}
                    {item.updated_at ? new Date(item.updated_at).toLocaleDateString("pt-BR") : "—"}
                    {isActive && (
                      <span className="ml-1.5 text-emerald-400/90">· aberto</span>
                    )}
                  </p>
                </button>

                <span className="shrink-0 text-right text-sm font-semibold text-emerald-400">
                  R$ {fmt(item.grand_total)}
                </span>

                <button
                  type="button"
                  onClick={() => {
                    onSelect(item.id);
                    onOpen(item.id);
                  }}
                  className="shrink-0 rounded p-1.5 text-slate-400 hover:bg-cyan-500/10 hover:text-cyan-300"
                  title="Abrir para editar"
                  aria-label={`Editar ${item.title}`}
                >
                  <IconPencil className="h-4 w-4" />
                </button>

                <button
                  type="button"
                  onClick={() => onDelete(item.id)}
                  className="shrink-0 rounded p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-400"
                  title="Excluir"
                  aria-label={`Excluir ${item.title}`}
                >
                  <IconTrash className="h-4 w-4" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
