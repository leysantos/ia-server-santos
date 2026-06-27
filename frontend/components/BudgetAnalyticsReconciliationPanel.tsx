"use client";

import {
  formatBrl,
  formatBrlCompact,
  reconcileBudgetAnalytics,
  type BudgetAnalyticsReconciliation,
} from "@/lib/budget-analytics";
import type { BudgetRow, ProjectSchedule } from "@/types/api";
import { cn } from "@/lib/utils";

export function BudgetAnalyticsReconciliationPanel({
  schedule,
  rows,
  histogramTotal,
  histogramTotalWithBdi,
  className,
}: {
  schedule?: ProjectSchedule | null;
  rows: BudgetRow[];
  histogramTotal?: number;
  histogramTotalWithBdi?: number;
  className?: string;
}) {
  const r = reconcileBudgetAnalytics(schedule, rows);

  return (
    <div
      className={cn(
        "rounded-lg bg-slate-950/50 px-3 py-2.5 text-[11px] ring-1 ring-slate-800/80",
        className
      )}
    >
      <p className="font-medium text-slate-400">Conferência com o orçamento</p>
      <dl className="mt-2 grid gap-1 sm:grid-cols-2">
        <Row label="Serviços (S)" value={`${r.serviceCount}`} />
        <Row label="Total efetivo (ABC / sintético)" value={formatBrl(r.serviceTotalEffective)} />
        <Row label="Custo unitário × qtd (sem BDI)" value={formatBrl(r.serviceTotalUnitCost)} />
        {r.scurveFinancialTotal > 0 && (
          <Row label="Curva S — financeiro total" value={formatBrl(r.scurveFinancialTotal)} />
        )}
        {histogramTotal != null && histogramTotal > 0 && (
          <Row label="Histograma — custo analítico CPU" value={formatBrl(histogramTotal)} />
        )}
        {histogramTotalWithBdi != null && histogramTotalWithBdi > 0 && (
          <Row label="Histograma — ref. com BDI" value={formatBrl(histogramTotalWithBdi)} />
        )}
      </dl>
      {r.unscheduledValue > 0.01 && (
        <p className="mt-2 text-amber-300/90">
          {formatBrlCompact(r.unscheduledValue)} em {r.unscheduledServices.length} serviço(s) sem
          tarefa no cronograma — alocado(s) no 1º mês da Curva S:{" "}
          {r.unscheduledServices.map((s) => s.code).join(", ")}
        </p>
      )}
      {histogramTotal != null && r.serviceTotalUnitCost > 0 && (
        <p className="mt-1 text-slate-500">
          Barras: custo analítico das CPUs (sem BDI). Linha tracejada: total efetivo rateado (com
          BDI por serviço). Diferença barras vs custo unitário:{" "}
          {formatBrl(Math.abs(histogramTotal - r.serviceTotalUnitCost))}
          {histogramTotal < r.serviceTotalUnitCost - 1 ? " (verifique CPUs não carregadas)" : ""}.
        </p>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="tabular-nums text-slate-200">{value}</dd>
    </div>
  );
}
