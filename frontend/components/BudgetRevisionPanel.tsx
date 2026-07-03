"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/services/api";
import type { BudgetBaselineCompare, BudgetRevisionItem, BudgetSessionResponse } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetBtn } from "@/lib/budget-ui";

interface BudgetRevisionPanelProps {
  budgetId: string;
  session: BudgetSessionResponse;
  disabled?: boolean;
  onOpenRevision: (session: BudgetSessionResponse) => void;
  onSessionUpdate?: (session: BudgetSessionResponse) => void;
  onError?: (err: unknown, title?: string) => void;
}

function fmt(n: number) {
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function BudgetRevisionPanel({
  budgetId,
  session,
  disabled,
  onOpenRevision,
  onSessionUpdate,
  onError,
}: BudgetRevisionPanelProps) {
  const [revisions, setRevisions] = useState<BudgetRevisionItem[]>([]);
  const [compare, setCompare] = useState<BudgetBaselineCompare | null>(null);
  const [loading, setLoading] = useState(false);

  const frozen = session.baseline_frozen === true;
  const revisionLabel = session.revision_label;

  const refresh = useCallback(() => {
    void api.pricingListRevisions(budgetId).then((r) => setRevisions(r.items)).catch(() => {});
    if (frozen || session.baseline_document_id) {
      void api
        .pricingBaselineCompare(budgetId)
        .then((r) => setCompare(r.comparison))
        .catch(() => setCompare(null));
    } else {
      setCompare(null);
    }
  }, [budgetId, frozen, session.baseline_document_id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleFreeze = async () => {
    setLoading(true);
    try {
      await api.pricingFreezeBaseline(budgetId);
      const loaded = await api.pricingGetSaved(budgetId);
      onSessionUpdate?.(loaded);
      refresh();
    } catch (err) {
      onError?.(err, "Falha ao congelar baseline");
    } finally {
      setLoading(false);
    }
  };

  const handleNewRevision = async () => {
    setLoading(true);
    try {
      const result = await api.pricingCreateRevision(budgetId);
      if (result.session) onOpenRevision(result.session);
      refresh();
    } catch (err) {
      onError?.(err, "Falha ao criar revisão");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-xl bg-slate-800/30 p-4 ring-1 ring-teal-500/25">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-teal-100">Revisões contratuais (aditivos)</h3>
          <p className="mt-1 text-xs text-slate-500">
            Congele a baseline antes de abrir aditivos. A baseline fica somente leitura.
          </p>
          {revisionLabel && (
            <p className="mt-2 text-xs text-teal-300/90">
              Revisão atual: <span className="font-medium">{revisionLabel}</span>
              {frozen ? " · baseline congelada" : ""}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {!frozen && (
            <button
              type="button"
              disabled={disabled || loading}
              onClick={() => void handleFreeze()}
              className={cn(
                budgetBtn,
                "bg-teal-600/20 px-3 py-1.5 text-xs text-teal-100 ring-teal-500/40 hover:bg-teal-600/30"
              )}
            >
              Congelar baseline
            </button>
          )}
          {frozen && (
            <button
              type="button"
              disabled={disabled || loading}
              onClick={() => void handleNewRevision()}
              className={cn(
                budgetBtn,
                "bg-cyan-600/20 px-3 py-1.5 text-xs text-cyan-100 ring-cyan-500/40 hover:bg-cyan-600/30"
              )}
            >
              Nova revisão (aditivo)
            </button>
          )}
        </div>
      </div>

      {compare && (
        <div className="mt-4 rounded-lg border border-white/5 bg-slate-900/50 px-3 py-2 text-xs text-slate-300">
          <span className="text-slate-500">Δ total vs baseline: </span>
          <span className={compare.delta_grand_total >= 0 ? "text-amber-300" : "text-emerald-300"}>
            {fmt(compare.delta_grand_total)}
          </span>
          {compare.delta_pct != null && (
            <span className="ml-2 text-slate-500">({compare.delta_pct}%)</span>
          )}
          <span className="ml-3 text-slate-500">{compare.lines_changed} linha(s) alterada(s)</span>
        </div>
      )}

      {revisions.length > 0 && (
        <ul className="mt-4 space-y-1 text-xs">
          {revisions.map((r) => (
            <li
              key={r.id}
              className={cn(
                "flex items-center justify-between rounded px-2 py-1.5",
                r.id === budgetId ? "bg-teal-500/10 text-teal-100" : "text-slate-400"
              )}
            >
              <span>
                {r.revision_label || `Rev ${r.revision_number ?? 0}`} — {r.title}
              </span>
              <span className="font-mono text-slate-500">{fmt(r.grand_total)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
