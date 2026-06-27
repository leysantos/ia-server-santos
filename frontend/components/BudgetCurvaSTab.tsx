"use client";

import { useMemo } from "react";
import type { BudgetSessionResponse } from "@/types/api";
import { buildScurvePoints, formatBrlCompact } from "@/lib/budget-analytics";
import { BudgetLineChart, ChartLegend } from "@/components/BudgetChartPrimitives";
import { BudgetAnalyticsReconciliationPanel } from "@/components/BudgetAnalyticsReconciliationPanel";
import BudgetAnalyticsExportActions from "@/components/BudgetAnalyticsExportActions";
import { fmtCurrency } from "@/lib/schedule-curves";
import { cn } from "@/lib/utils";

interface BudgetCurvaSTabProps {
  session: BudgetSessionResponse;
  onExportPdf?: (docKey: string, label: string) => void;
  onExportExcel?: (docKey: string, label: string) => void;
  exportDisabled?: boolean;
}

export default function BudgetCurvaSTab({
  session,
  onExportPdf,
  onExportExcel,
  exportDisabled,
}: BudgetCurvaSTabProps) {
  const schedule = session.schedule;
  const rows = session.rows ?? [];

  const { points, totalFinancial, hasSchedule } = useMemo(
    () => buildScurvePoints(schedule, rows),
    [schedule, rows]
  );

  if (!hasSchedule) {
    return (
      <div className="rounded-xl bg-slate-900/40 p-8 text-center ring-1 ring-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Curva S</h3>
        <p className="mt-2 text-sm text-slate-400">
          Sincronize o cronograma na aba Cronograma (datas de início/fim e tarefas vinculadas aos
          serviços) para visualizar a evolução física e financeira acumulada por mês.
        </p>
      </div>
    );
  }

  const lastPhysical = points[points.length - 1]?.physicalCumulativePct ?? 0;
  const lastFinancial = points[points.length - 1]?.financialCumulativePct ?? 0;

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Curva S — avanço acumulado</h3>
            <p className="mt-1 text-xs text-slate-500">
              Distribuição mensal proporcional à duração das tarefas no cronograma. Físico ponderado
              pela quantidade dos serviços; financeiro pelo valor efetivo.
            </p>
          </div>
          <BudgetAnalyticsExportActions
            docKey="curva_s"
            label="Curva S"
            disabled={exportDisabled}
            onExportPdf={onExportPdf}
            onExportExcel={onExportExcel}
          />
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg bg-slate-950/40 px-3 py-2 ring-1 ring-slate-800/80">
            <p className="text-[10px] uppercase tracking-wide text-slate-500">Valor total</p>
            <p className="mt-1 text-lg font-semibold tabular-nums text-amber-200">
              {fmtCurrency(totalFinancial)}
            </p>
          </div>
          <div className="rounded-lg bg-slate-950/40 px-3 py-2 ring-1 ring-slate-800/80">
            <p className="text-[10px] uppercase tracking-wide text-slate-500">Físico acumulado (fim)</p>
            <p className="mt-1 text-lg font-semibold tabular-nums text-emerald-200">
              {lastPhysical.toFixed(1)}%
            </p>
          </div>
          <div className="rounded-lg bg-slate-950/40 px-3 py-2 ring-1 ring-slate-800/80">
            <p className="text-[10px] uppercase tracking-wide text-slate-500">Financeiro acum. (fim)</p>
            <p className="mt-1 text-lg font-semibold tabular-nums text-cyan-200">
              {lastFinancial.toFixed(1)}%
            </p>
          </div>
        </div>

        <BudgetAnalyticsReconciliationPanel
          className="mt-4"
          schedule={schedule}
          rows={rows}
        />

        <ChartLegend
          className="mt-4"
          items={[
            { label: "Avanço físico acumulado", color: "#10b981" },
            { label: "Desembolso financeiro acumulado", color: "#38bdf8" },
          ]}
        />

        <div className="mt-4 overflow-x-auto">
          <BudgetLineChart
            labels={points.map((p) => p.label)}
            series={[
              {
                name: "Físico",
                color: "#10b981",
                values: points.map((p) => p.physicalCumulativePct),
              },
              {
                name: "Financeiro",
                color: "#38bdf8",
                values: points.map((p) => p.financialCumulativePct),
              },
            ]}
            renderTooltip={(index) => {
              const point = points[index];
              if (!point) return null;
              return <ScurveTooltipContent point={point} monthIndex={index + 1} />;
            }}
          />
        </div>
        <p className="mt-2 text-[10px] text-slate-600">
          Passe o mouse sobre os meses para ver avanço mensal e acumulado.
        </p>
      </div>

      <div className="overflow-hidden rounded-xl ring-1 ring-slate-800">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-900/80 text-slate-500">
            <tr>
              <th className="px-3 py-2 font-medium">Mês</th>
              <th className="px-3 py-2 text-right font-medium">Físico acum.</th>
              <th className="px-3 py-2 text-right font-medium">Financeiro acum.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 bg-slate-950/30">
            {points.map((p) => (
              <tr key={p.label}>
                <td className="px-3 py-2 text-slate-300">{p.label}</td>
                <td className="px-3 py-2 text-right tabular-nums text-emerald-300/90">
                  {p.physicalCumulativePct.toFixed(2)}%
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-cyan-300/90">
                  {p.financialCumulativePct.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ScurveTooltipContent({
  point,
  monthIndex,
}: {
  point: {
    label: string;
    physicalMonthlyPct: number;
    physicalCumulativePct: number;
    financialMonthly: number;
    financialCumulative: number;
    financialCumulativePct: number;
  };
  monthIndex: number;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-slate-200">{point.label}</span>
        <span className="text-[10px] text-slate-500">Mês {monthIndex}</span>
      </div>
      <div className="space-y-1 border-t border-slate-700/60 pt-1.5 text-[10px]">
        <p className="text-[9px] uppercase tracking-wide text-emerald-500/80">Avanço físico</p>
        <TooltipRow label="Mensal" value={`${point.physicalMonthlyPct.toFixed(2)}%`} />
        <TooltipRow
          label="Acumulado"
          value={`${point.physicalCumulativePct.toFixed(2)}%`}
          accent="emerald"
        />
      </div>
      <div className="space-y-1 border-t border-slate-700/60 pt-1.5 text-[10px]">
        <p className="text-[9px] uppercase tracking-wide text-cyan-500/80">Desembolso financeiro</p>
        <TooltipRow label="Mensal" value={formatBrlCompact(point.financialMonthly)} />
        <TooltipRow
          label="Acumulado"
          value={formatBrlCompact(point.financialCumulative)}
          accent="cyan"
        />
        <TooltipRow
          label="Acum. (%)"
          value={`${point.financialCumulativePct.toFixed(2)}%`}
          accent="cyan"
        />
      </div>
    </div>
  );
}

function TooltipRow({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "emerald" | "cyan";
}) {
  const valueColor =
    accent === "emerald"
      ? "text-emerald-300"
      : accent === "cyan"
        ? "text-cyan-300"
        : "text-slate-200";
  return (
    <div className="flex justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className={cn("tabular-nums font-medium", valueColor)}>{value}</span>
    </div>
  );
}
