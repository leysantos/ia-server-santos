"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/services/api";
import type { ComplianceChecklistItem, CompliancePackPreview } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetBtn } from "@/lib/budget-ui";

const STATUS_STYLES: Record<string, string> = {
  ok: "text-emerald-300 bg-emerald-500/10 ring-emerald-500/30",
  revisar: "text-rose-300 bg-rose-500/10 ring-rose-500/30",
  atencao: "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  pendente: "text-slate-400 bg-slate-500/10 ring-slate-500/30",
  manual: "text-sky-300 bg-sky-500/10 ring-sky-500/30",
};

interface BudgetCompliancePanelProps {
  sessionId: string;
  disabled?: boolean;
  onDownload?: () => void;
  onError?: (err: unknown, title?: string) => void;
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    ok: "OK",
    revisar: "Revisar",
    atencao: "Atenção",
    pendente: "Pendente",
    manual: "Manual",
  };
  return map[status] ?? status;
}

export default function BudgetCompliancePanel({
  sessionId,
  disabled,
  onDownload,
  onError,
}: BudgetCompliancePanelProps) {
  const [pack, setPack] = useState<CompliancePackPreview | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.pricingFetchCompliancePack(sessionId);
      setPack(data);
    } catch (err) {
      onError?.(err, "Falha ao carregar pacote compliance");
    } finally {
      setLoading(false);
    }
  }, [sessionId, onError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const checklist = pack?.checklist_lei_14133 ?? [];

  return (
    <section
      className="space-y-4 rounded-xl bg-sky-500/5 p-4 ring-1 ring-sky-500/25"
      data-testid="budget-compliance-panel"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-sky-200">Compliance licitação (Lei 14.133)</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Checklist técnico L1–L7 · PNCP e prestação de contas permanecem fluxo institucional.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={disabled || loading}
            onClick={() => void refresh()}
            className={cn(budgetBtn, "px-3 py-1.5 text-xs text-sky-200 ring-sky-500/30 hover:bg-sky-500/10")}
          >
            Atualizar
          </button>
          {onDownload && (
            <button
              type="button"
              disabled={disabled || loading}
              onClick={onDownload}
              data-testid="budget-compliance-download"
              className={cn(
                budgetBtn,
                "bg-sky-600/20 px-3 py-1.5 text-xs text-sky-100 ring-sky-500/40 hover:bg-sky-600/30"
              )}
            >
              Baixar JSON
            </button>
          )}
        </div>
      </div>

      {loading && !pack && (
        <p className="text-xs text-slate-500">Carregando checklist…</p>
      )}

      {checklist.length > 0 && (
        <ul className="space-y-2" data-testid="budget-compliance-checklist">
          {checklist.map((item: ComplianceChecklistItem) => (
            <li
              key={item.id}
              className="flex items-center justify-between gap-3 rounded-lg bg-slate-900/40 px-3 py-2 text-xs"
              data-testid={`budget-compliance-item-${item.id}`}
            >
              <span className="text-slate-300">
                <span className="font-mono text-slate-500">{item.id}</span> — {item.item}
              </span>
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase ring-1",
                  STATUS_STYLES[item.status] ?? STATUS_STYLES.pendente
                )}
              >
                {statusLabel(item.status)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {pack?.export_official_xlsm === false && (
        <p className="text-[11px] text-amber-400/90">
          Workbook `.xlsm` oficial ainda não sincronizado — use &quot;PPD oficial (.xlsm)&quot; na toolbar.
        </p>
      )}
    </section>
  );
}
