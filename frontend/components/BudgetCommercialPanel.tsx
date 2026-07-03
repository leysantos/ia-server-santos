"use client";

import type { BudgetProjectInfo } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetField, budgetFieldLabel, budgetInput } from "@/lib/budget-ui";

export interface CommercialFormValues {
  commercial_margin_pct: number;
  commercial_client: string;
}

interface BudgetCommercialPanelProps {
  project?: BudgetProjectInfo;
  grandTotal?: number;
  disabled?: boolean;
  onChange: (values: CommercialFormValues) => void;
}

export function projectToCommercial(project?: BudgetProjectInfo): CommercialFormValues {
  return {
    commercial_margin_pct: Number(project?.commercial_margin_pct ?? 0) || 0,
    commercial_client: project?.commercial_client ?? "",
  };
}

function fmtBrl(value: number) {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function BudgetCommercialPanel({
  project,
  grandTotal = 0,
  disabled,
  onChange,
}: BudgetCommercialPanelProps) {
  const values = projectToCommercial(project);
  const set = (patch: Partial<CommercialFormValues>) => onChange({ ...values, ...patch });
  const marginValue = grandTotal > 0 ? (grandTotal * values.commercial_margin_pct) / 100 : 0;
  const proposalTotal = grandTotal + marginValue;

  return (
    <div
      className="space-y-4 rounded-xl bg-violet-500/5 p-4 ring-1 ring-violet-500/25"
      data-testid="budget-commercial-panel"
    >
      <div>
        <h3 className="text-sm font-semibold text-violet-200">Proposta comercial (CPQ)</h3>
        <p className="mt-0.5 text-xs text-slate-500">
          Margem sobre o custo direto do orçamento. Use o export &quot;Proposta comercial&quot; na toolbar.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <label className={budgetField}>
          <span className={budgetFieldLabel}>Margem comercial (%)</span>
          <input
            type="number"
            min={0}
            max={100}
            step={0.1}
            disabled={disabled}
            value={values.commercial_margin_pct || ""}
            onChange={(e) => set({ commercial_margin_pct: parseFloat(e.target.value) || 0 })}
            data-testid="budget-commercial-margin"
            className={cn(budgetInput, "font-mono")}
            placeholder="0"
          />
        </label>
        <label className={budgetField}>
          <span className={budgetFieldLabel}>Cliente / contratante privado</span>
          <input
            type="text"
            disabled={disabled}
            value={values.commercial_client}
            onChange={(e) => set({ commercial_client: e.target.value })}
            data-testid="budget-commercial-client"
            className={budgetInput}
            placeholder="Nome do cliente"
          />
        </label>
      </div>
      {grandTotal > 0 && values.commercial_margin_pct > 0 && (
        <dl className="grid gap-1 text-xs text-slate-400 sm:grid-cols-3" data-testid="budget-commercial-preview">
          <div>
            <dt>Custo direto</dt>
            <dd className="font-mono text-slate-200">{fmtBrl(grandTotal)}</dd>
          </div>
          <div>
            <dt>Margem ({values.commercial_margin_pct.toFixed(1)}%)</dt>
            <dd className="font-mono text-violet-200">{fmtBrl(marginValue)}</dd>
          </div>
          <div>
            <dt>Total proposta</dt>
            <dd className="font-mono font-semibold text-emerald-300">{fmtBrl(proposalTotal)}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}
