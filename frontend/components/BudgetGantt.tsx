"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { BudgetRow, ProjectSchedule, ScheduleTask } from "@/types/api";
import {
  buildProjectTimeline,
  buildScheduleCurvesByMonth,
  computeTaskMetrics,
  daysBetween,
  filterScheduleTasks,
  fmtCurrency,
  fmtCurrencyCompact,
  fmtPct,
  formatIsoDateBr,
  monthTimelineWidths,
  totalPhysicalPctForView,
  type ScheduleViewMode,
  type TaskScheduleMetrics,
} from "@/lib/schedule-curves";
import { cn } from "@/lib/utils";

const LABEL_W = 300;
const VALUE_W = 58;
const PCT_W = 44;
const ROW_H = 26;
const CURVE_ROW_H = 30;
const MONTH_HEADER_H = 22;
const WEEK_HEADER_H = 22;
const HEADER_H = MONTH_HEADER_H + WEEK_HEADER_H;

interface BudgetGanttProps {
  schedule: ProjectSchedule;
  budgetRows: BudgetRow[];
  viewMode?: ScheduleViewMode;
  selectedTaskId?: string | null;
  onSelectTask?: (taskId: string) => void;
}

export default function BudgetGantt({
  schedule,
  budgetRows,
  viewMode = "completo",
  selectedTaskId,
  onSelectTask,
}: BudgetGanttProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bodyScrollRef = useRef<HTMLDivElement>(null);
  const headerScrollRef = useRef<HTMLDivElement>(null);
  const [timelineWidth, setTimelineWidth] = useState(600);

  const projectEnd = schedule.project_end || schedule.project_start;

  const timeline = useMemo(
    () => buildProjectTimeline(schedule.project_start, projectEnd),
    [schedule.project_start, projectEnd]
  );

  const weekWidth = Math.max(
    24,
    Math.floor(timelineWidth / Math.max(1, timeline.weekCount))
  );

  const visibleTasks = useMemo(
    () => filterScheduleTasks(schedule.tasks, viewMode),
    [schedule.tasks, viewMode]
  );

  const { months, totalFinancial } = useMemo(
    () => buildScheduleCurvesByMonth(schedule, budgetRows, visibleTasks),
    [schedule, budgetRows, visibleTasks]
  );

  const { byTaskId } = useMemo(
    () => computeTaskMetrics(schedule, budgetRows, visibleTasks),
    [schedule, budgetRows, visibleTasks]
  );

  const visiblePhysicalPctSum = useMemo(
    () => totalPhysicalPctForView(schedule, visibleTasks, byTaskId),
    [schedule, visibleTasks, byTaskId]
  );

  const maxMonthlyFinancial = useMemo(
    () => Math.max(1, ...months.map((m) => m.financialMonthly)),
    [months]
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width - LABEL_W;
      if (w > 0) setTimelineWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const syncHeaderScroll = () => {
    if (bodyScrollRef.current && headerScrollRef.current) {
      headerScrollRef.current.scrollLeft = bodyScrollRef.current.scrollLeft;
    }
  };

  const totalTimelinePx = timeline.weekCount * weekWidth;
  const totalDays = timeline.totalDays;

  const monthCurveWidths = useMemo(
    () => monthTimelineWidths(months, schedule.project_start, projectEnd, totalTimelinePx),
    [months, schedule.project_start, projectEnd, totalTimelinePx]
  );

  return (
    <div
      ref={containerRef}
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl ring-1 ring-slate-700/60"
    >
      <div className="flex shrink-0 flex-col border-b border-slate-700/60 bg-slate-900/95">
        <div className="flex">
          <LabelHeader height={HEADER_H} />
          <div ref={headerScrollRef} className="min-w-0 flex-1 overflow-hidden">
            <div style={{ width: totalTimelinePx }}>
              <div className="flex border-b border-slate-800/50">
                {timeline.monthGroups.map((mg) => (
                  <div
                    key={mg.monthKey}
                    style={{ width: mg.weekCount * weekWidth, height: MONTH_HEADER_H }}
                    className="flex shrink-0 items-center justify-center border-r border-slate-800/80 text-[10px] font-medium capitalize text-slate-400"
                  >
                    {mg.label}
                  </div>
                ))}
              </div>
              <div className="flex">
                {timeline.weeks.map((w) => (
                  <div
                    key={w.weekIndex}
                    style={{ width: weekWidth, height: WEEK_HEADER_H }}
                    className="flex shrink-0 flex-col items-center justify-center border-r border-slate-800/60 text-[8px] leading-tight text-slate-500"
                  >
                    <span className="font-mono text-slate-600">{w.label}</span>
                    <span>{w.dateLabel}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        ref={bodyScrollRef}
        onScroll={syncHeaderScroll}
        className="min-h-0 flex-1 overflow-auto"
      >
        <div className="flex" style={{ minWidth: LABEL_W + totalTimelinePx }}>
          <div
            className="sticky left-0 z-[2] shrink-0 border-r border-slate-700/60 bg-slate-950"
            style={{ width: LABEL_W }}
          >
            {visibleTasks.map((task) => (
              <TaskLabel
                key={task.task_id}
                task={task}
                metrics={byTaskId.get(task.task_id)}
                height={ROW_H}
                selected={selectedTaskId === task.task_id}
                onSelect={onSelectTask}
              />
            ))}
            <CurveLabel
              title="Físico acum."
              height={CURVE_ROW_H}
              accent="emerald"
              totalValue={null}
              totalPct={visiblePhysicalPctSum}
              pctOnly
            />
            <CurveLabel
              title="Desembolso mês"
              height={CURVE_ROW_H}
              accent="amber"
              totalValue={totalFinancial}
              totalPct={100}
            />
            <CurveLabel
              title="Financeiro acum."
              height={CURVE_ROW_H}
              accent="cyan"
              totalValue={totalFinancial}
              totalPct={100}
            />
          </div>

          <div style={{ width: totalTimelinePx }} className="shrink-0">
            {visibleTasks.map((task) => (
              <TimelineRow
                key={task.task_id}
                task={task}
                projectStart={schedule.project_start}
                weekCount={timeline.weekCount}
                weekWidth={weekWidth}
                totalDays={totalDays}
                height={ROW_H}
                selected={selectedTaskId === task.task_id}
                onSelect={onSelectTask}
              />
            ))}

            <div
              className="flex border-b border-slate-800/50 bg-emerald-950/20"
              style={{ width: totalTimelinePx, height: CURVE_ROW_H }}
            >
              {months.map((m, i) =>
                monthCurveWidths[i] > 0 ? (
                  <div
                    key={m.monthIndex}
                    style={{ width: monthCurveWidths[i] }}
                    className="relative flex shrink-0 flex-col items-center justify-end border-r border-slate-800/40 pb-0.5"
                  >
                  <div
                    className="absolute bottom-0 left-1 right-1 rounded-t bg-emerald-500/50"
                    style={{
                      height: `${Math.min(100, m.physicalCumulativePct)}%`,
                      maxHeight: CURVE_ROW_H - 16,
                    }}
                  />
                  <span className="relative z-[1] text-[7px] font-medium text-emerald-300">
                    {fmtPct(m.physicalMonthlyPct)}
                  </span>
                  <span className="relative z-[1] text-[7px] text-emerald-400/80">
                    {m.physicalCumulativePct.toFixed(0)}%
                  </span>
                </div>
                ) : null
              )}
            </div>

            <div
              className="flex border-b border-slate-800/50 bg-amber-950/15"
              style={{ width: totalTimelinePx, height: CURVE_ROW_H }}
            >
              {months.map((m, i) => {
                if (monthCurveWidths[i] <= 0) return null;
                const finPct =
                  totalFinancial > 0 ? (m.financialMonthly / totalFinancial) * 100 : 0;
                return (
                  <div
                    key={m.monthIndex}
                    style={{ width: monthCurveWidths[i] }}
                    className="relative flex shrink-0 flex-col items-center justify-end border-r border-slate-800/40 pb-0.5"
                  >
                    <div
                      className="absolute bottom-0 left-1/2 w-[65%] -translate-x-1/2 rounded-t bg-amber-500/55"
                      style={{
                        height: `${Math.max(4, (m.financialMonthly / maxMonthlyFinancial) * (CURVE_ROW_H - 16))}px`,
                      }}
                    />
                    <span className="relative z-[1] text-[7px] text-amber-200">
                      {fmtCurrencyCompact(m.financialMonthly)}
                    </span>
                    <span className="relative z-[1] text-[7px] text-amber-300/80">
                      {fmtPct(finPct)}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="flex bg-cyan-950/15" style={{ width: totalTimelinePx, height: CURVE_ROW_H }}>
              {months.map((m, i) => {
                if (monthCurveWidths[i] <= 0) return null;
                const cumPct =
                  totalFinancial > 0 ? (m.financialCumulative / totalFinancial) * 100 : 0;
                return (
                  <div
                    key={m.monthIndex}
                    style={{ width: monthCurveWidths[i] }}
                    className="relative flex shrink-0 flex-col items-center justify-end border-r border-slate-800/40 pb-0.5"
                  >
                    <div
                      className="absolute bottom-0 left-1 right-1 rounded-t bg-cyan-500/40"
                      style={{
                        height: `${
                          totalFinancial > 0
                            ? (m.financialCumulative / totalFinancial) * (CURVE_ROW_H - 16)
                            : 0
                        }px`,
                      }}
                    />
                    <span className="relative z-[1] text-[7px] text-cyan-300">
                      {fmtCurrencyCompact(m.financialCumulative)}
                    </span>
                    <span className="relative z-[1] text-[7px] text-cyan-400/80">
                      {fmtPct(cumPct)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LabelHeader({ height }: { height: number }) {
  return (
    <div
      style={{ width: LABEL_W, height }}
      className="flex shrink-0 items-center border-r border-slate-700/60 bg-slate-900/95 text-[9px] font-medium uppercase tracking-wider text-slate-500"
    >
      <span className="min-w-0 flex-1 truncate px-2">Tarefa</span>
      <span
        style={{ width: VALUE_W }}
        className="shrink-0 border-l border-slate-800/60 px-1 text-right"
      >
        Valor
      </span>
      <span
        style={{ width: PCT_W }}
        className="shrink-0 border-l border-slate-800/60 px-1 text-right"
      >
        %
      </span>
    </div>
  );
}

function TaskLabel({
  task,
  metrics,
  height,
  selected,
  onSelect,
}: {
  task: ScheduleTask;
  metrics?: TaskScheduleMetrics;
  height: number;
  selected?: boolean;
  onSelect?: (id: string) => void;
}) {
  const indent = task.is_summary ? (task.row_type === "ETAPA" ? 0 : 1) : 2;
  const cost = metrics?.cost ?? 0;
  const pct = metrics?.financialPct ?? 0;

  return (
    <button
      type="button"
      onClick={() => onSelect?.(task.task_id)}
      style={{ height, paddingLeft: 4 + indent * 6 }}
      className={cn(
        "flex w-full items-center gap-0 border-b border-slate-800/40 text-left text-[10px] transition hover:bg-slate-800/40",
        selected && "bg-cyan-500/10",
        task.is_summary && "bg-slate-900/50 font-medium"
      )}
      title={`${task.budget_code} ${task.name} · ${fmtCurrency(cost)} · ${fmtPct(pct)}`}
    >
      <span
        className={cn(
          "w-7 shrink-0 truncate font-mono text-[9px]",
          task.is_summary
            ? task.row_type === "ETAPA"
              ? "text-violet-400"
              : "text-cyan-400"
            : "text-slate-500"
        )}
      >
        {task.budget_code}
      </span>
      <span className="min-w-0 flex-1 truncate pr-1 text-slate-300">{task.name}</span>
      <span
        style={{ width: VALUE_W }}
        className="shrink-0 border-l border-slate-800/30 px-1 text-right font-mono text-[9px] text-amber-200/90"
      >
        {cost > 0 ? fmtCurrencyCompact(cost) : "—"}
      </span>
      <span
        style={{ width: PCT_W }}
        className="shrink-0 border-l border-slate-800/30 px-1 text-right font-mono text-[9px] text-cyan-300/90"
      >
        {cost > 0 ? fmtPct(pct) : "—"}
      </span>
    </button>
  );
}

function CurveLabel({
  title,
  height,
  accent,
  totalValue,
  totalPct,
  pctOnly,
}: {
  title: string;
  height: number;
  accent: "emerald" | "amber" | "cyan";
  totalValue: number | null;
  totalPct: number;
  pctOnly?: boolean;
}) {
  const colors = {
    emerald: "text-emerald-400/90",
    amber: "text-amber-400/90",
    cyan: "text-cyan-400/90",
  };
  const valueColors = {
    emerald: "text-emerald-300/80",
    amber: "text-amber-200/90",
    cyan: "text-cyan-300/90",
  };

  return (
    <div
      style={{ height }}
      className="flex items-center border-b border-slate-800/40 bg-slate-900/30 text-[9px] font-medium"
    >
      <span className={cn("min-w-0 flex-1 truncate px-2 uppercase tracking-wide", colors[accent])}>
        Σ {title}
      </span>
      <span
        style={{ width: VALUE_W }}
        className={cn(
          "shrink-0 border-l border-slate-800/30 px-1 text-right font-mono",
          pctOnly ? "text-slate-600" : valueColors[accent]
        )}
      >
        {pctOnly ? "—" : totalValue != null && totalValue > 0 ? fmtCurrencyCompact(totalValue) : "—"}
      </span>
      <span
        style={{ width: PCT_W }}
        className={cn(
          "shrink-0 border-l border-slate-800/30 px-1 text-right font-mono",
          valueColors[accent]
        )}
      >
        {fmtPct(totalPct)}
      </span>
    </div>
  );
}

function TimelineRow({
  task,
  projectStart,
  weekCount,
  weekWidth,
  totalDays,
  height,
  selected,
  onSelect,
}: {
  task: ScheduleTask;
  projectStart: string;
  weekCount: number;
  weekWidth: number;
  totalDays: number;
  height: number;
  selected?: boolean;
  onSelect?: (id: string) => void;
}) {
  const start = task.early_start;
  const finish = task.early_finish;
  const hasBar = start && finish;
  const totalW = weekCount * weekWidth;

  let leftPx = 0;
  let widthPx = weekWidth;
  if (hasBar) {
    const startDay = daysBetween(projectStart, start);
    const endDay = daysBetween(projectStart, finish);
    leftPx = (startDay / totalDays) * totalW;
    widthPx = Math.max(4, ((endDay - startDay + 1) / totalDays) * totalW);
  }

  return (
    <div
      style={{ height, width: totalW }}
      className={cn(
        "relative shrink-0 border-b border-slate-800/30",
        selected && "bg-cyan-500/5",
        task.is_summary && "bg-slate-900/15"
      )}
      onClick={() => onSelect?.(task.task_id)}
    >
      <div className="absolute inset-0 flex">
        {Array.from({ length: weekCount }).map((_, i) => (
          <div
            key={i}
            style={{ width: weekWidth }}
            className="h-full shrink-0 border-r border-slate-800/25"
          />
        ))}
      </div>
      {hasBar && (
        <div
          className={cn(
            "absolute top-1 flex h-[calc(100%-8px)] items-center overflow-hidden rounded-sm px-0.5 text-[8px] font-medium text-white",
            task.is_summary
              ? "bg-violet-600/45 ring-1 ring-violet-400/30"
              : task.is_critical
                ? "bg-red-600/75 ring-1 ring-red-400/40"
                : "bg-cyan-600/60 ring-1 ring-cyan-400/30"
          )}
          style={{ left: leftPx, width: widthPx }}
          title={`${formatIsoDateBr(start)} → ${formatIsoDateBr(finish)} · ${task.duration_days}d`}
        >
          {widthPx > 40 && <span className="truncate">{task.duration_days}d</span>}
        </div>
      )}
    </div>
  );
}
