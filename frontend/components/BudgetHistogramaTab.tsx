"use client";

import { useMemo } from "react";
import type { BudgetSessionResponse } from "@/types/api";
import {
  buildHistogramItemStacks,
  buildHistogramReport,
  formatHistogramQty,
  type HistogramItemRow,
  type HistogramReportModel,
  type HistogramSectionModel,
} from "@/lib/budget-analytics";
import { BudgetStackedBarChart, ChartLegend } from "@/components/BudgetChartPrimitives";
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

function sectionHasData(section: HistogramSectionModel | null): boolean {
  if (!section) return false;
  return section.items.some((item) => item.total > 0.0001);
}

function reportHasData(model: HistogramReportModel): boolean {
  return sectionHasData(model.maoObra) || sectionHasData(model.equipamento);
}

export default function BudgetHistogramaTab({
  session,
  onExportPdf,
  onExportExcel,
  exportDisabled,
}: BudgetHistogramaTabProps) {
  const { loaded, loading, progress, errorCount, loadKey } = useBudgetServiceCompositions(session);

  const compositionLoadState = `${loaded.size}|${progress.done}|${loading ? 1 : 0}`;

  const modelCacheKey = useMemo(
    () =>
      histogramModelCacheKey(
        session.session_id ?? "",
        `${loadKey}|${compositionLoadState}`,
        "comd",
        session.schedule
      ),
    [session.session_id, loadKey, compositionLoadState, session.schedule]
  );

  const model = useMemo(() => {
    if (!loading) {
      const cached = getCachedHistogramModel(modelCacheKey);
      if (cached && reportHasData(cached)) return cached;
    }

    const built = buildHistogramReport(
      session.schedule,
      session.rows ?? [],
      loaded,
      session.project
    );

    if (!loading && built.hasSchedule && reportHasData(built)) {
      setCachedHistogramModel(modelCacheKey, built);
    }
    return built;
  }, [
    modelCacheKey,
    session.schedule,
    session.rows,
    session.project,
    loaded,
    loading,
  ]);

  if (!model.hasSchedule) {
    return (
      <div className="rounded-xl bg-slate-900/40 p-8 text-center ring-1 ring-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Histograma de mão de obra e equipamentos</h3>
        <p className="mt-2 text-sm text-slate-400">
          Sincronize o cronograma na aba Cronograma para visualizar a demanda mensal por item de mão de
          obra e equipamentos.
        </p>
      </div>
    );
  }

  const hasData = reportHasData(model);

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">
              Histograma de mão de obra e equipamentos
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Tabela por item com quantidades mensais (dias acumulados da obra) e gráfico empilhado —
              conforme planilha Caixa.
            </p>
            <p className="mt-1 text-xs text-slate-600">
              CLIENTE: {model.clientLabel} — {model.projectLabel}
            </p>
          </div>
          <BudgetAnalyticsExportActions
            docKey="histograma"
            label="Histograma"
            disabled={exportDisabled || loading}
            onExportPdf={onExportPdf}
            onExportExcel={onExportExcel}
          />
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

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MiniStat label="Serviços com CPU" value={String(model.servicesWithCpu)} />
          <MiniStat
            label="Itens MO"
            value={String(model.maoObra?.items.length ?? 0)}
          />
          <MiniStat
            label="Itens equipamentos"
            value={String(model.equipamento?.items.length ?? 0)}
          />
          <MiniStat
            label="Períodos"
            value={String(
              model.maoObra?.columns.length ?? model.equipamento?.columns.length ?? 0
            )}
          />
        </div>
      </div>

      {hasData ? (
        <div className="space-y-6">
          {model.maoObra && sectionHasData(model.maoObra) && (
            <HistogramSectionPanel section={model.maoObra} />
          )}
          {model.equipamento && sectionHasData(model.equipamento) && (
            <HistogramSectionPanel section={model.equipamento} />
          )}
        </div>
      ) : (
        <div className="rounded-xl bg-slate-900/40 p-8 text-center ring-1 ring-slate-800">
          <p className="text-sm text-slate-500">
            Nenhum dado de MO ou equipamento. Verifique serviços, CPUs e cronograma.
          </p>
        </div>
      )}
    </div>
  );
}

function HistogramSectionPanel({ section }: { section: HistogramSectionModel }) {
  const periodLabels = section.columns.map((c) => String(c.periodDay));
  const stacks = useMemo(() => buildHistogramItemStacks(section), [section]);

  return (
    <div className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
      <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-200">
        {section.title}
      </h4>
      <p className="mt-1 text-xs text-slate-500">
        {section.chartYLabel} rateados pelo cronograma · colunas em dias acumulados da obra
      </p>

      <div className="mt-4 overflow-x-auto rounded-lg ring-1 ring-slate-800">
        <table className="w-full min-w-[720px] text-left text-xs">
          <thead className="bg-slate-900/80 text-slate-500">
            <tr>
              <th className="px-3 py-2 font-medium">ITENS</th>
              <th className="px-3 py-2 font-medium">DISCRIMINAÇÃO</th>
              {section.columns.map((col) => (
                <th key={col.monthIndex} className="px-2 py-2 text-center font-medium tabular-nums">
                  {col.periodDay}
                </th>
              ))}
              <th className="px-3 py-2 text-center font-medium">TOTAL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 bg-slate-950/30">
            {section.items.map((item) => (
              <HistogramItemTableRow key={item.itemKey} item={item} columnCount={section.columns.length} />
            ))}
            <tr className="bg-slate-900/60 font-semibold text-slate-100">
              <td className="px-3 py-2" colSpan={2}>
                TOTAL
              </td>
              {section.monthlyTotals.map((val, i) => (
                <td key={i} className="px-2 py-2 text-center tabular-nums">
                  {formatHistogramQty(val)}
                </td>
              ))}
              <td className="px-3 py-2 text-center tabular-nums">
                {formatHistogramQty(section.monthlyTotals.reduce((s, v) => s + v, 0))}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="mt-6">
        <ChartLegend
          className="mb-3 flex-wrap justify-center gap-x-4 gap-y-1"
          items={stacks.map((s) => ({ label: s.label, color: s.color }))}
        />
        <p className="mb-2 text-center text-xs font-medium text-slate-400">
          {section.chartYLabel}
        </p>
        <div className="overflow-x-auto">
          <BudgetStackedBarChart
            periodLabels={periodLabels}
            stacks={stacks}
            renderTooltip={(index) => (
              <SectionMonthTooltip section={section} stacks={stacks} monthIndex={index} />
            )}
          />
        </div>
      </div>
    </div>
  );
}

function HistogramItemTableRow({
  item,
  columnCount,
}: {
  item: HistogramItemRow;
  columnCount: number;
}) {
  return (
    <tr className="hover:bg-slate-900/40">
      <td className="px-3 py-2 text-center tabular-nums text-slate-400">{item.index}</td>
      <td className="px-3 py-2 text-slate-300">
        {item.description}
        {item.unit ? (
          <span className="ml-1 text-[10px] text-slate-600">({item.unit})</span>
        ) : null}
      </td>
      {Array.from({ length: columnCount }, (_, i) => (
        <td key={i} className="px-2 py-2 text-center tabular-nums text-slate-300">
          {formatHistogramQty(item.monthlyValues[i] ?? 0)}
        </td>
      ))}
      <td className="px-3 py-2 text-center tabular-nums font-medium text-slate-200">
        {formatHistogramQty(item.total)}
      </td>
    </tr>
  );
}

function SectionMonthTooltip({
  section,
  stacks,
  monthIndex,
}: {
  section: HistogramSectionModel;
  stacks: ReturnType<typeof buildHistogramItemStacks>;
  monthIndex: number;
}) {
  const col = section.columns[monthIndex];
  if (!col) return null;

  const total = stacks.reduce((s, st) => s + (st.values[monthIndex] ?? 0), 0);

  return (
    <div className="space-y-2">
      <div>
        <p className="font-medium text-slate-100">{col.label}</p>
        <p className="text-[10px] text-slate-500">Dia {col.periodDay} da obra</p>
      </div>
      <div className="space-y-1 border-t border-slate-700/60 pt-1.5 text-[10px]">
        {stacks.map((st) => {
          const val = st.values[monthIndex] ?? 0;
          if (val <= 0) return null;
          return (
            <div key={st.key} className="flex justify-between gap-3">
              <span className="inline-flex items-center gap-1.5 text-slate-400">
                <span
                  className="inline-block h-2 w-2 rounded-sm"
                  style={{ backgroundColor: st.color }}
                />
                {st.label}
              </span>
              <span className="tabular-nums font-medium text-slate-200">
                {formatHistogramQty(val)}
              </span>
            </div>
          );
        })}
        <div className="flex justify-between gap-3 border-t border-slate-700/40 pt-1 font-semibold">
          <span className="text-slate-400">Total</span>
          <span className="tabular-nums text-cyan-300">{formatHistogramQty(total)}</span>
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-950/40 px-3 py-2 ring-1 ring-slate-800/80">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-base font-semibold tabular-nums text-slate-200">{value}</p>
    </div>
  );
}
