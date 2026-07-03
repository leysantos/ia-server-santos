"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/services/api";
import type { BudgetAuditEntry } from "@/types/api";

interface BudgetAuditTabProps {
  sessionId: string;
}

function formatValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number") return String(value);
  return String(value);
}

export default function BudgetAuditTab({ sessionId }: BudgetAuditTabProps) {
  const [items, setItems] = useState<BudgetAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    api
      .pricingBudgetAudit(sessionId)
      .then((r) => setItems(r.items ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar auditoria"))
      .finally(() => setLoading(false));
  }, [sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (loading) {
    return <p className="py-8 text-center text-sm text-slate-500">Carregando trilha de auditoria…</p>;
  }

  if (error) {
    return (
      <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
        {error}
      </div>
    );
  }

  if ((items?.length ?? 0) === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        Nenhuma alteração registrada ainda — edite células ou aplique BDI para gerar trilha.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl ring-1 ring-slate-700/50">
      <div className="max-h-[480px] overflow-y-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-slate-900/95 text-slate-400">
            <tr>
              <th className="px-3 py-2 font-medium">Quando</th>
              <th className="px-3 py-2 font-medium">Ação</th>
              <th className="px-3 py-2 font-medium">Linha</th>
              <th className="px-3 py-2 font-medium">Campo</th>
              <th className="px-3 py-2 font-medium">De → Para</th>
            </tr>
          </thead>
          <tbody>
            {items.map((entry, idx) => (
              <tr key={entry.id ?? `${entry.created_at}-${idx}`} className="border-t border-white/5">
                <td className="whitespace-nowrap px-3 py-2 text-slate-500">
                  {entry.created_at
                    ? new Date(entry.created_at).toLocaleString("pt-BR")
                    : entry.at
                      ? new Date(entry.at).toLocaleString("pt-BR")
                      : "—"}
                </td>
                <td className="px-3 py-2 text-violet-200">{entry.action}</td>
                <td className="px-3 py-2 font-mono text-cyan-300/90">
                  {entry.row_code || entry.row_id || "—"}
                </td>
                <td className="px-3 py-2 text-slate-400">{entry.field || "—"}</td>
                <td className="px-3 py-2 text-slate-300">
                  {entry.action === "bdi_change" ? (
                    <span>
                      ComD {formatValue(entry.meta?.old_rate_comd)} → {formatValue(entry.meta?.new_rate_comd ?? entry.new_rate_comd)}
                      {" · "}
                      SemD {formatValue(entry.meta?.old_rate_semd)} → {formatValue(entry.meta?.new_rate_semd ?? entry.new_rate_semd)}
                    </span>
                  ) : (
                    <span>
                      {formatValue(entry.old_value)} → {formatValue(entry.new_value)}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
