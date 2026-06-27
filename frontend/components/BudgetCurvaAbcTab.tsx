"use client";

import { useMemo } from "react";
import type { BudgetSessionResponse } from "@/types/api";
import {
  buildAbcCurve,
  formatBrlCompact,
  type AbcClass,
} from "@/lib/budget-analytics";
import { BudgetParetoChart } from "@/components/BudgetChartPrimitives";
import { BudgetAnalyticsReconciliationPanel } from "@/components/BudgetAnalyticsReconciliationPanel";
import BudgetAnalyticsExportActions from "@/components/BudgetAnalyticsExportActions";
import { cn } from "@/lib/utils";

const ABC_CLASS_COLORS: Record<AbcClass, string> = {
  A: "#10b981",
  B: "#f59e0b",
  C: "#64748b",
};

interface BudgetCurvaAbcTabProps {
  session: BudgetSessionResponse;
  onExportPdf?: (docKey: string, label: string) => void;
  onExportExcel?: (docKey: string, label: string) => void;
  exportDisabled?: boolean;
}

export default function BudgetCurvaAbcTab({
  session,
  onExportPdf,
  onExportExcel,
  exportDisabled,
}: BudgetCurvaAbcTabProps) {
  const items = useMemo(() => buildAbcCurve(session.rows ?? []), [session.rows]);

  const summary = useMemo(() => {
    const total = items.reduce((s, i) => s + i.value, 0);
    const byClass = { A: 0, B: 0, C: 0 } as Record<AbcClass, number>;
    for (const item of items) byClass[item.abcClass] += item.value;
    return { total, byClass, count: items.length };
  }, [items]);

  const topChart = items.slice(0, 20);

  if (items.length === 0) {
    return (
      <div className="rounded-xl bg-slate-900/40 p-8 text-center ring-1 ring-slate-800">
        <p className="text-sm text-slate-400">
          Lance serviços nas etapas para gerar a curva ABC do orçamento.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Curva ABC</h3>
            <p className="mt-1 text-xs text-slate-500">
              Classificação Pareto dos serviços por valor (ComD/efetivo). Classe A até 80% acumulado,
              B até 95%, C restante.
            </p>
          </div>
          <BudgetAnalyticsExportActions
            docKey="curva_abc"
            label="Curva ABC"
            disabled={exportDisabled}
            onExportPdf={onExportPdf}
            onExportExcel={onExportExcel}
          />
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          <StatCard label="Total serviços" value={String(summary.count)} />
          <StatCard label="Valor total" value={formatBrlCompact(summary.total)} accent="amber" />
          <StatCard
            label="Classe A"
            value={formatBrlCompact(summary.byClass.A)}
            sub={`${summary.total > 0 ? ((summary.byClass.A / summary.total) * 100).toFixed(1) : 0}%`}
            accent="emerald"
          />
          <StatCard
            label="Classes B + C"
            value={formatBrlCompact(summary.byClass.B + summary.byClass.C)}
            accent="slate"
          />
        </div>

        <BudgetAnalyticsReconciliationPanel
          className="mt-4"
          schedule={session.schedule}
          rows={session.rows ?? []}
        />

        <div className="mt-6 overflow-x-auto">
          <BudgetParetoChart
            labels={topChart.map((i) => i.code)}
            barValues={topChart.map((i) => i.value)}
            cumulativePct={topChart.map((i) => i.cumulativePct)}
            barColors={topChart.map((i) => ABC_CLASS_COLORS[i.abcClass])}
            renderTooltip={(index) => {
              const item = topChart[index];
              if (!item) return null;
              return <AbcTooltipContent item={item} rank={index + 1} />;
            }}
          />
        </div>
        <p className="mt-2 text-[10px] text-slate-600">
          Gráfico: top 20 serviços · passe o mouse para ver o resumo · barras = valor · linha azul = %
          acumulado
        </p>
      </div>

      <div className="overflow-hidden rounded-xl ring-1 ring-slate-800">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-900/80 text-slate-500">
            <tr>
              <th className="px-3 py-2 font-medium">Classe</th>
              <th className="px-3 py-2 font-medium">Código</th>
              <th className="px-3 py-2 font-medium">Descrição</th>
              <th className="px-3 py-2 text-right font-medium">Valor</th>
              <th className="px-3 py-2 text-right font-medium">%</th>
              <th className="px-3 py-2 text-right font-medium">Acum.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 bg-slate-950/30">
            {items.map((item) => (
              <tr key={item.row_id} className="hover:bg-slate-900/40">
                <td className="px-3 py-2">
                  <span
                    className={cn(
                      "inline-flex rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold",
                      item.abcClass === "A" && "bg-emerald-500/15 text-emerald-300",
                      item.abcClass === "B" && "bg-amber-500/15 text-amber-300",
                      item.abcClass === "C" && "bg-slate-600/30 text-slate-400"
                    )}
                  >
                    {item.abcClass}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-cyan-400/90">{item.code}</td>
                <td className="max-w-md px-3 py-2 text-slate-300">{item.name}</td>
                <td className="px-3 py-2 text-right tabular-nums text-amber-200/90">
                  {formatBrlCompact(item.value)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                  {item.pct.toFixed(2)}%
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-cyan-300/90">
                  {item.cumulativePct.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AbcTooltipContent({
  item,
  rank,
}: {
  item: {
    code: string;
    name: string;
    value: number;
    pct: number;
    cumulativePct: number;
    abcClass: AbcClass;
  };
  rank: number;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] text-cyan-400">{item.code}</span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 font-mono text-[9px] font-semibold",
            item.abcClass === "A" && "bg-emerald-500/20 text-emerald-300",
            item.abcClass === "B" && "bg-amber-500/20 text-amber-300",
            item.abcClass === "C" && "bg-slate-600/40 text-slate-400"
          )}
        >
          Classe {item.abcClass}
        </span>
      </div>
      <p className="line-clamp-2 text-slate-200">{item.name}</p>
      <div className="space-y-0.5 border-t border-slate-700/60 pt-1.5 text-[10px]">
        <TooltipRow label="Posição" value={`#${rank}`} />
        <TooltipRow label="Valor" value={formatBrlCompact(item.value)} accent="amber" />
        <TooltipRow label="Participação" value={`${item.pct.toFixed(2)}%`} />
        <TooltipRow label="Acumulado" value={`${item.cumulativePct.toFixed(2)}%`} accent="cyan" />
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
  accent?: "amber" | "cyan";
}) {
  const valueColor =
    accent === "amber" ? "text-amber-200" : accent === "cyan" ? "text-cyan-300" : "text-slate-200";
  return (
    <div className="flex justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className={cn("tabular-nums font-medium", valueColor)}>{value}</span>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  accent = "slate",
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "slate" | "amber" | "emerald";
}) {
  const colors = {
    slate: "text-slate-200",
    amber: "text-amber-200",
    emerald: "text-emerald-200",
  };
  return (
    <div className="rounded-lg bg-slate-950/40 px-3 py-2 ring-1 ring-slate-800/80">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={cn("mt-1 text-lg font-semibold tabular-nums", colors[accent])}>{value}</p>
      {sub && <p className="text-[10px] text-slate-500">{sub}</p>}
    </div>
  );
}
