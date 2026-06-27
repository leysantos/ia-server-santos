"use client";

import { useMemo, useState } from "react";
import type { BudgetSessionResponse } from "@/types/api";
import {
  buildStackedHistogram,
  formatBrl,
  formatBrlCompact,
  RESOURCE_CATEGORY_COLORS,
  RESOURCE_CATEGORY_LABELS,
  type ResourceCategory,
  type StackedHistogramMonth,
} from "@/lib/budget-analytics";
import { BudgetStackedBarChart, ChartLegend } from "@/components/BudgetChartPrimitives";
import { BudgetAnalyticsReconciliationPanel } from "@/components/BudgetAnalyticsReconciliationPanel";
import BudgetAnalyticsExportActions from "@/components/BudgetAnalyticsExportActions";
import { useBudgetServiceCompositions } from "@/hooks/useBudgetServiceCompositions";
import LoadingSpinner from "@/components/LoadingSpinner";
import {
  getCachedHistogramModel,
  histogramModelCacheKey,
  setCachedHistogramModel,
} from "@/lib/budget-histogram-cache";

interface BudgetHistogramaTabProps {
  session: BudgetSessionResponse;
  onExportPdf?: (docKey: string, label: string) => void;
  onExportExcel?: (docKey: string, label: string) => void;
  exportDisabled?: boolean;
}

const STACK_ORDER: ResourceCategory[] = ["insumo", "equipamento", "mao_obra"];

export default function BudgetHistogramaTab({
  session,
  onExportPdf,
  onExportExcel,
  exportDisabled,
}: BudgetHistogramaTabProps) {
  const [priceMode, setPriceMode] = useState<"comd" | "semd">("comd");
  const { loaded, loading, progress, errorCount, loadKey } = useBudgetServiceCompositions(session);

  const modelCacheKey = useMemo(
    () =>
      histogramModelCacheKey(
        session.session_id ?? "",
        loadKey,
        priceMode,
        session.schedule
      ),
    [session.session_id, loadKey, priceMode, session.schedule]
  );

  const model = useMemo(() => {
    if (!loading) {
      const cached = getCachedHistogramModel(modelCacheKey);
      if (cached) return cached;
    }

    const built = buildStackedHistogram(
      session.schedule,
      session.rows ?? [],
      loaded,
      priceMode,
      session.project
    );

    if (!loading && built.hasSchedule) {
      setCachedHistogramModel(modelCacheKey, built);
    }
    return built;
  }, [
    modelCacheKey,
    session.schedule,
    session.rows,
    session.project,
    loaded,
    priceMode,
    loading,
  ]);

  const stacks = useMemo(
    () =>
      STACK_ORDER.map((cat) => ({
        key: cat,
        label: RESOURCE_CATEGORY_LABELS[cat],
        color: RESOURCE_CATEGORY_COLORS[cat],
        values: model.months.map((m) => m[cat]),
      })),
    [model.months]
  );

  if (!model.hasSchedule) {
    return (
      <div className="rounded-xl bg-slate-900/40 p-8 text-center ring-1 ring-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Histograma de demanda</h3>
        <p className="mt-2 text-sm text-slate-400">
          Sincronize o cronograma na aba Cronograma para visualizar a demanda mensal de insumos,
          equipamentos e mão de obra.
        </p>
      </div>
    );
  }

  const hasData = model.months.some((m) => m.total > 0);

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Histograma de demanda</h3>
            <p className="mt-1 text-xs text-slate-500">
              Barras verticais empilhadas por mês — insumos, equipamentos e mão de obra (custos das
              CPUs rateados pelo cronograma).
            </p>
            <p className="mt-1 text-xs text-slate-600">
              CLIENTE: {model.clientLabel} — {model.projectLabel}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <BudgetAnalyticsExportActions
              docKey="histograma"
              label="Histograma"
              disabled={exportDisabled || loading}
              onExportPdf={onExportPdf}
              onExportExcel={onExportExcel}
            />
            <label className="text-sm text-slate-400">
            Preços
            <select
              value={priceMode}
              onChange={(e) => setPriceMode(e.target.value as "comd" | "semd")}
              className="ml-2 rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
            >
              <option value="comd">Com desoneração</option>
              <option value="semd">Sem desoneração</option>
            </select>
          </label>
          </div>
        </div>

        {loading && (
          <div className="mt-4 flex items-center gap-3 text-xs text-slate-500">
            <LoadingSpinner size="sm" />
            Carregando CPUs ({progress.done}/{progress.total})…
          </div>
        )}

        {!loading && errorCount > 0 && (
          <p className="mt-3 text-xs text-amber-300/90">
            {errorCount} serviço(s) sem CPU carregada — verifique bases de preço e códigos.
          </p>
        )}

        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          <MiniStat label="Serviços com CPU" value={String(model.servicesWithCpu)} />
          {STACK_ORDER.map((cat) => (
            <MiniStat
              key={cat}
              label={RESOURCE_CATEGORY_LABELS[cat]}
              value={formatBrlCompact(model.totals[cat])}
              color={RESOURCE_CATEGORY_COLORS[cat]}
            />
          ))}
        </div>

        <ChartLegend
          className="mt-4 justify-center"
          items={[
            ...STACK_ORDER.map((cat) => ({
              label: RESOURCE_CATEGORY_LABELS[cat],
              color: RESOURCE_CATEGORY_COLORS[cat],
            })),
            ...(model.totals.totalWithBdi > 0
              ? [{ label: "Ref. com BDI", color: "#f472b6" }]
              : []),
          ]}
        />

        {hasData ? (
          <>
            <BudgetAnalyticsReconciliationPanel
              className="mt-4"
              schedule={session.schedule}
              rows={session.rows ?? []}
              histogramTotal={model.totals.total}
              histogramTotalWithBdi={model.totals.totalWithBdi}
            />
            <div className="mt-4 overflow-x-auto">
              <BudgetStackedBarChart
                periodLabels={model.months.map((m) => String(m.periodDay))}
                stacks={stacks}
                referenceSeries={
                  model.totals.totalWithBdi > 0
                    ? {
                        label: "Ref. com BDI",
                        color: "#f472b6",
                        values: model.months.map((m) => m.totalWithBdi),
                      }
                    : undefined
                }
                renderTooltip={(index) => (
                  <StackedMonthTooltip month={model.months[index]} />
                )}
              />
            </div>
            <p className="mt-2 text-center text-[10px] text-slate-600">
              Eixo horizontal: dia acumulado da obra · Eixo vertical: custo (R$) · linha tracejada =
              referência com BDI · passe o mouse sobre as barras
            </p>
          </>
        ) : (
          <p className="mt-6 py-8 text-center text-sm text-slate-500">
            Nenhum custo analítico disponível. Verifique serviços, CPUs e cronograma.
          </p>
        )}
      </div>

      {hasData && (
        <div className="overflow-hidden rounded-xl ring-1 ring-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/80 text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">Mês</th>
                <th className="px-3 py-2 text-right font-medium">Insumos</th>
                <th className="px-3 py-2 text-right font-medium">Equipamentos</th>
                <th className="px-3 py-2 text-right font-medium">Mão de obra</th>
                <th className="px-3 py-2 text-right font-medium">Total</th>
                <th className="px-3 py-2 text-right font-medium">Ref. BDI</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-950/30">
              {model.months.map((m) => (
                <tr key={m.monthIndex} className="hover:bg-slate-900/40">
                  <td className="px-3 py-2 text-slate-300">
                    {m.label}
                    <span className="ml-1 text-[10px] text-slate-600">(d{m.periodDay})</span>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-emerald-200/90">
                    {formatBrlCompact(m.insumo)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-amber-200/90">
                    {formatBrlCompact(m.equipamento)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-cyan-200/90">
                    {formatBrlCompact(m.mao_obra)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-200">
                    {formatBrlCompact(m.total)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-pink-200/90">
                    {formatBrlCompact(m.totalWithBdi)}
                  </td>
                </tr>
              ))}
              <tr className="bg-slate-900/60 font-semibold text-slate-100">
                <td className="px-3 py-2">Total geral</td>
                <td className="px-3 py-2 text-right tabular-nums text-emerald-200/90">
                  {formatBrlCompact(model.totals.insumo)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-amber-200/90">
                  {formatBrlCompact(model.totals.equipamento)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-cyan-200/90">
                  {formatBrlCompact(model.totals.mao_obra)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatBrlCompact(model.totals.total)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-pink-200/90">
                  {formatBrlCompact(model.totals.totalWithBdi)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StackedMonthTooltip({ month }: { month: StackedHistogramMonth | undefined }) {
  if (!month) return null;

  const rows: { cat: ResourceCategory; value: number }[] = STACK_ORDER.map((cat) => ({
    cat,
    value: month[cat],
  })).filter((r) => r.value > 0);

  return (
    <div className="space-y-2">
      <div>
        <p className="font-medium text-slate-100">{month.label}</p>
        <p className="text-[10px] text-slate-500">Dia {month.periodDay} da obra</p>
      </div>
      <div className="space-y-1 border-t border-slate-700/60 pt-1.5 text-[10px]">
        {rows.map(({ cat, value }) => (
          <div key={cat} className="flex justify-between gap-3">
            <span className="inline-flex items-center gap-1.5 text-slate-400">
              <span
                className="inline-block h-2 w-2 rounded-sm"
                style={{ backgroundColor: RESOURCE_CATEGORY_COLORS[cat] }}
              />
              {RESOURCE_CATEGORY_LABELS[cat]}
            </span>
            <span className="tabular-nums font-medium text-slate-200">{formatBrl(value)}</span>
          </div>
        ))}
        <div className="flex justify-between gap-3 border-t border-slate-700/40 pt-1 font-semibold">
          <span className="text-slate-400">Total (CPU)</span>
          <span className="tabular-nums text-cyan-300">{formatBrl(month.total)}</span>
        </div>
        {month.totalWithBdi > 0 && (
          <div className="flex justify-between gap-3 text-[10px]">
            <span className="text-pink-300/80">Ref. com BDI</span>
            <span className="tabular-nums font-medium text-pink-200">{formatBrl(month.totalWithBdi)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="rounded-lg bg-slate-950/40 px-3 py-2 ring-1 ring-slate-800/80">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p
        className="mt-1 text-base font-semibold tabular-nums"
        style={color ? { color } : undefined}
      >
        {value}
      </p>
    </div>
  );
}
