import type { BudgetRow, ProjectSchedule, ScheduleTask } from "@/types/api";

export interface MonthBucket {
  monthIndex: number;
  label: string;
  monthStartIso: string;
  monthEndIso: string;
  physicalMonthlyPct: number;
  physicalCumulativePct: number;
  financialMonthly: number;
  financialCumulative: number;
}

/** @deprecated use MonthBucket — kept for compat during migration */
export interface WeekBucket {
  weekIndex: number;
  label: string;
  weekStartIso: string;
  physicalWeeklyPct: number;
  physicalCumulativePct: number;
  financialWeekly: number;
  financialCumulative: number;
}

function parseDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

function daysBetween(start: string, end: string): number {
  const a = parseDate(start);
  const b = parseDate(end);
  return Math.round((b.getTime() - a.getTime()) / 86400000);
}

function addDays(iso: string, days: number): string {
  const d = parseDate(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function overlapDays(
  rangeStart: string,
  rangeEnd: string,
  periodStart: string,
  periodEnd: string
): number {
  const rs = parseDate(rangeStart).getTime();
  const re = parseDate(rangeEnd).getTime();
  const ps = parseDate(periodStart).getTime();
  const pe = parseDate(periodEnd).getTime();
  const start = Math.max(rs, ps);
  const end = Math.min(re, pe);
  if (end < start) return 0;
  return Math.round((end - start) / 86400000) + 1;
}

function monthStartDate(projectStart: string, monthIndex: number): Date {
  const s = parseDate(projectStart);
  return new Date(s.getFullYear(), s.getMonth() + monthIndex, 1);
}

function monthEndDate(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

function formatIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function countMonths(projectStart: string, projectEnd: string): number {
  const s = parseDate(projectStart);
  const e = parseDate(projectEnd);
  return Math.max(1, (e.getFullYear() - s.getFullYear()) * 12 + (e.getMonth() - s.getMonth()) + 1);
}

export function monthLabel(d: Date): string {
  return d.toLocaleDateString("pt-BR", { month: "short", year: "2-digit" });
}

/** Exibe data ISO (YYYY-MM-DD) no padrão brasileiro dd/mm/aaaa */
export function formatIsoDateBr(iso?: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  if (!y || !m || !d) return iso;
  return `${d.padStart(2, "0")}/${m.padStart(2, "0")}/${y}`;
}

export interface TimelineWeekColumn {
  weekIndex: number;
  label: string;
  dateLabel: string;
  weekStartIso: string;
  weekEndIso: string;
  monthKey: string;
}

export interface TimelineMonthGroup {
  monthIndex: number;
  label: string;
  weekCount: number;
  monthKey: string;
}

export function countProjectWeeks(projectStart: string, projectEnd: string): number {
  const totalDays = Math.max(1, daysBetween(projectStart, projectEnd || projectStart) + 1);
  return Math.ceil(totalDays / 7);
}

export function buildProjectTimeline(
  projectStart: string,
  projectEnd: string
): {
  weeks: TimelineWeekColumn[];
  monthGroups: TimelineMonthGroup[];
  weekCount: number;
  totalDays: number;
} {
  const end = projectEnd || projectStart;
  const totalDays = Math.max(1, daysBetween(projectStart, end) + 1);
  const weekCount = Math.ceil(totalDays / 7);
  const weeks: TimelineWeekColumn[] = [];

  for (let w = 0; w < weekCount; w++) {
    const weekStart = addDays(projectStart, w * 7);
    const weekEnd = addDays(projectStart, Math.min(w * 7 + 6, totalDays - 1));
    const startDate = parseDate(weekStart);
    const monthKey = `${startDate.getFullYear()}-${String(startDate.getMonth() + 1).padStart(2, "0")}`;
    weeks.push({
      weekIndex: w,
      label: `S${w + 1}`,
      dateLabel: formatIsoDateBr(weekStart),
      weekStartIso: weekStart,
      weekEndIso: weekEnd,
      monthKey,
    });
  }

  const monthGroups: TimelineMonthGroup[] = [];
  for (const week of weeks) {
    const last = monthGroups[monthGroups.length - 1];
    if (!last || last.monthKey !== week.monthKey) {
      monthGroups.push({
        monthIndex: monthGroups.length,
        label: monthLabel(parseDate(week.weekStartIso)),
        weekCount: 1,
        monthKey: week.monthKey,
      });
    } else {
      last.weekCount += 1;
    }
  }

  return { weeks, monthGroups, weekCount, totalDays };
}

export function weeksOverlappingPeriod(
  weeks: TimelineWeekColumn[],
  periodStart: string,
  periodEnd: string
): number {
  let n = 0;
  for (const w of weeks) {
    if (overlapDays(w.weekStartIso, w.weekEndIso, periodStart, periodEnd) > 0) n += 1;
  }
  return n;
}

function clipToProject(
  periodStart: string,
  periodEnd: string,
  projectStart: string,
  projectEnd: string
): { start: string; end: string } | null {
  const end = projectEnd || projectStart;
  const start = periodStart < projectStart ? projectStart : periodStart;
  const finish = periodEnd > end ? end : periodEnd;
  if (start > finish) return null;
  return { start, end: finish };
}

/** Larguras das colunas mensais alinhadas ao timeline (soma = totalTimelinePx). */
export function monthTimelineWidths(
  months: MonthBucket[],
  projectStart: string,
  projectEnd: string,
  totalTimelinePx: number
): number[] {
  if (months.length === 0 || totalTimelinePx <= 0) return [];

  const end = projectEnd || projectStart;
  const dayWeights = months.map((m) => {
    const clip = clipToProject(m.monthStartIso, m.monthEndIso, projectStart, end);
    if (!clip) return 0;
    return daysBetween(clip.start, clip.end) + 1;
  });

  const weightSum = dayWeights.reduce((a, b) => a + b, 0) || 1;
  const widths = dayWeights.map((d) =>
    d <= 0 ? 0 : Math.max(1, Math.floor((d / weightSum) * totalTimelinePx))
  );

  let sum = widths.reduce((a, b) => a + b, 0);
  for (let i = widths.length - 1; sum < totalTimelinePx && i >= 0; i--) {
    if (dayWeights[i] > 0) {
      widths[i] += 1;
      sum += 1;
    }
  }
  for (let i = widths.length - 1; sum > totalTimelinePx && i >= 0; i--) {
    if (widths[i] > 1) {
      widths[i] -= 1;
      sum -= 1;
    }
  }

  return widths;
}

function rowForTask(rows: BudgetRow[], task: ScheduleTask): BudgetRow | undefined {
  return rows.find((r) => r.row_id === task.budget_row_id);
}

function leafTaskForService(schedule: ProjectSchedule, rowId: string): ScheduleTask | undefined {
  return schedule.tasks.find(
    (t) => t.budget_row_id === rowId && !t.is_summary && t.early_start && t.early_finish
  );
}

function servicePhysicalWeight(row: BudgetRow): number {
  const qty = Math.max(0, row.quantity ?? 1);
  return qty > 0 ? qty : 1;
}

function serviceFinancialCost(row: BudgetRow): number {
  return row.total_effective ?? row.total_price ?? 0;
}

/** Serviços (S) sem tarefa folha com datas no cronograma */
export function unscheduledServiceRows(
  schedule: ProjectSchedule,
  rows: BudgetRow[]
): BudgetRow[] {
  return rows.filter(
    (r) =>
      r.row_type === "S" && !r.is_memory_row && !leafTaskForService(schedule, r.row_id)
  );
}

function leafTasksForCurve(
  schedule: ProjectSchedule,
  visibleTasks?: ScheduleTask[]
): ScheduleTask[] {
  const allLeaves = schedule.tasks.filter(
    (t) => !t.is_summary && t.early_start && t.early_finish
  );
  if (!visibleTasks?.length) return allLeaves;

  const etapaOnly = visibleTasks.every((t) => t.is_summary && t.row_type === "ETAPA");
  if (!etapaOnly) {
    const ids = new Set(visibleTasks.map((t) => t.task_id));
    return allLeaves.filter((t) => ids.has(t.task_id));
  }

  return visibleTasks
    .filter((t) => t.early_start && t.early_finish)
    .map((etapa) => ({
      ...etapa,
      duration_days: Math.max(
        1,
        daysBetween(etapa.early_start!, etapa.early_finish!) + 1
      ),
    }));
}

function weightAndCost(
  task: ScheduleTask,
  rows: BudgetRow[],
  _etapaMode?: boolean
): { weight: number; cost: number } {
  if (task.is_summary) {
    const prefix = `${task.budget_code}.`;
    const children = rows.filter(
      (r) =>
        r.row_type === "S" &&
        !r.is_memory_row &&
        (r.code === task.budget_code || r.code.startsWith(prefix))
    );
    let weight = 0;
    let cost = 0;
    for (const row of children) {
      const qty = Math.max(0, row.quantity ?? 1);
      weight += qty > 0 ? qty : 1;
      cost += row.total_effective ?? row.total_price ?? 0;
    }
    if (weight <= 0) weight = children.length || 1;
    return { weight, cost };
  }

  const row = rowForTask(rows, task);
  const qty = Math.max(0, row?.quantity ?? 1);
  const weight = qty > 0 ? qty : 1;
  const cost = row?.total_effective ?? row?.total_price ?? 0;
  return { weight, cost };
}

export interface TaskScheduleMetrics {
  cost: number;
  financialPct: number;
  physicalPct: number;
}

export function computeTaskMetrics(
  schedule: ProjectSchedule,
  rows: BudgetRow[],
  visibleTasks: ScheduleTask[]
): {
  byTaskId: Map<string, TaskScheduleMetrics>;
  totalFinancial: number;
  totalPhysicalWeight: number;
} {
  const etapaOnly =
    visibleTasks.length > 0 &&
    visibleTasks.every((t) => t.is_summary && t.row_type === "ETAPA");

  const leaves = leafTasksForCurve(schedule, visibleTasks);
  let totalPhysicalWeight = 0;
  let totalFinancial = 0;

  for (const task of leaves) {
    const { weight, cost } = weightAndCost(task, rows, etapaOnly);
    totalPhysicalWeight += weight;
    totalFinancial += cost;
  }
  if (totalPhysicalWeight <= 0) totalPhysicalWeight = leaves.length || 1;

  const byTaskId = new Map<string, TaskScheduleMetrics>();
  for (const task of visibleTasks) {
    const { weight, cost } = weightAndCost(task, rows, etapaOnly);
    byTaskId.set(task.task_id, {
      cost,
      financialPct: totalFinancial > 0 ? (cost / totalFinancial) * 100 : 0,
      physicalPct: totalPhysicalWeight > 0 ? (weight / totalPhysicalWeight) * 100 : 0,
    });
  }

  return { byTaskId, totalFinancial, totalPhysicalWeight };
}

/** Soma % físico apenas das folhas da visão (evita dupla contagem etapa + serviços). */
export function totalPhysicalPctForView(
  schedule: ProjectSchedule,
  visibleTasks: ScheduleTask[],
  byTaskId: Map<string, TaskScheduleMetrics>
): number {
  const leaves = leafTasksForCurve(schedule, visibleTasks);
  const total = leaves.reduce(
    (sum, task) => sum + (byTaskId.get(task.task_id)?.physicalPct ?? 0),
    0
  );
  return Math.min(100, total);
}

export function buildScheduleCurvesByMonth(
  schedule: ProjectSchedule,
  rows: BudgetRow[],
  visibleTasks?: ScheduleTask[]
): { months: MonthBucket[]; totalFinancial: number; totalPhysicalWeight: number } {
  const projectStart = schedule.project_start;
  const projectEnd = schedule.project_end || projectStart;
  const monthCount = countMonths(projectStart, projectEnd);
  const leaves = leafTasksForCurve(schedule, visibleTasks);
  const etapaMode = Boolean(
    visibleTasks?.length &&
      visibleTasks.every((t) => t.is_summary && t.row_type === "ETAPA")
  );

  let totalPhysicalWeight = 0;
  let totalFinancial = 0;

  for (const task of leaves) {
    const { weight, cost } = weightAndCost(task, rows, etapaMode);
    totalPhysicalWeight += weight;
    totalFinancial += cost;
  }

  const orphans = unscheduledServiceRows(schedule, rows);
  let orphanWeight = 0;
  let orphanCost = 0;
  for (const row of orphans) {
    orphanWeight += servicePhysicalWeight(row);
    orphanCost += serviceFinancialCost(row);
  }
  totalPhysicalWeight += orphanWeight;
  totalFinancial += orphanCost;

  if (totalPhysicalWeight <= 0) totalPhysicalWeight = leaves.length || orphans.length || 1;

  const months: MonthBucket[] = [];
  let physicalCum = 0;
  let financialCum = 0;
  let orphansAllocated = false;

  for (let m = 0; m < monthCount; m++) {
    const mStart = monthStartDate(projectStart, m);
    const mEnd = monthEndDate(mStart);
    const periodStart = formatIso(mStart);
    const periodEnd = formatIso(mEnd);
    const clip = clipToProject(periodStart, periodEnd, projectStart, projectEnd);
    if (!clip) continue;

    let physicalMonth = 0;
    let financialMonth = 0;

    for (const task of leaves) {
      const { weight, cost } = weightAndCost(task, rows, etapaMode);
      const dur = Math.max(1, task.duration_days);
      const overlap = overlapDays(
        task.early_start!,
        task.early_finish!,
        clip.start,
        clip.end
      );
      if (overlap <= 0) continue;
      physicalMonth += (weight * overlap) / dur;
      financialMonth += (cost * overlap) / dur;
    }

    if (!orphansAllocated && (orphanWeight > 0 || orphanCost > 0)) {
      physicalMonth += orphanWeight;
      financialMonth += orphanCost;
      orphansAllocated = true;
    }

    const physicalMonthlyPct = (physicalMonth / totalPhysicalWeight) * 100;
    physicalCum = Math.min(100, physicalCum + physicalMonthlyPct);
    financialCum += financialMonth;

    months.push({
      monthIndex: months.length,
      label: monthLabel(mStart),
      monthStartIso: periodStart,
      monthEndIso: periodEnd,
      physicalMonthlyPct,
      physicalCumulativePct: physicalCum,
      financialMonthly: financialMonth,
      financialCumulative: financialCum,
    });
  }

  return { months, totalFinancial, totalPhysicalWeight };
}

/** @deprecated use buildScheduleCurvesByMonth */
export function buildScheduleCurves(
  schedule: ProjectSchedule,
  rows: BudgetRow[]
): { weeks: WeekBucket[]; totalFinancial: number; totalPhysicalWeight: number } {
  const { months, totalFinancial, totalPhysicalWeight } = buildScheduleCurvesByMonth(
    schedule,
    rows
  );
  const weeks: WeekBucket[] = months.map((m) => ({
    weekIndex: m.monthIndex,
    label: m.label,
    weekStartIso: m.monthStartIso,
    physicalWeeklyPct: m.physicalMonthlyPct,
    physicalCumulativePct: m.physicalCumulativePct,
    financialWeekly: m.financialMonthly,
    financialCumulative: m.financialCumulative,
  }));
  return { weeks, totalFinancial, totalPhysicalWeight };
}

/** @deprecated use countProjectWeeks */
export function countWeeks(projectStart: string, projectEnd: string): number {
  return countProjectWeeks(projectStart, projectEnd);
}

export function fmtCurrency(n: number): string {
  if (n >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `R$ ${(n / 1_000).toFixed(0)}k`;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}

export function fmtCurrencyCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

export function fmtPct(n: number): string {
  if (n >= 10) return `${n.toFixed(1)}%`;
  if (n >= 1) return `${n.toFixed(1)}%`;
  return n > 0 ? `${n.toFixed(2)}%` : "0%";
}

export type ScheduleViewMode = "etapas" | "completo";

export function filterScheduleTasks(
  tasks: ScheduleTask[],
  mode: ScheduleViewMode
): ScheduleTask[] {
  if (mode === "completo") return tasks;
  return tasks.filter((t) => t.is_summary && t.row_type === "ETAPA");
}

export { daysBetween, addDays, parseDate };
