import type {
  BudgetRow,
  OpenCompositionDetail,
  OpenCompositionItem,
  ProjectSchedule,
  ScheduleTask,
} from "@/types/api";
import {
  buildScheduleCurvesByMonth,
  daysBetween,
  type MonthBucket,
} from "@/lib/schedule-curves";
import { resolveResourceCategory, isHistogramDirectLabor } from "@/lib/budget-resource-classification";

export type ResourceCategory = "equipamento" | "insumo" | "mao_obra";

export const RESOURCE_CATEGORY_LABELS: Record<ResourceCategory, string> = {
  equipamento: "Equipamentos",
  insumo: "Insumos",
  mao_obra: "Mão de obra",
};

export const RESOURCE_CATEGORY_COLORS: Record<ResourceCategory, string> = {
  equipamento: "#f59e0b",
  insumo: "#10b981",
  mao_obra: "#38bdf8",
};

export type AbcClass = "A" | "B" | "C";

export interface AbcItem {
  row_id: string;
  code: string;
  name: string;
  value: number;
  pct: number;
  cumulativePct: number;
  abcClass: AbcClass;
}

export interface HistogramMeasure {
  quantity: number;
  value: number;
}

export interface ResourceMonthBucket {
  monthIndex: number;
  label: string;
  equipamento: number;
  insumo: number;
  mao_obra: number;
  total: number;
  /** Referência mensal com BDI (total efetivo rateado pelo cronograma) */
  totalWithBdi: number;
}

export interface StackedHistogramMonth {
  monthIndex: number;
  label: string;
  periodDay: number;
  equipamento: HistogramMeasure;
  mao_obra: HistogramMeasure;
}

export interface HistogramMonthColumn {
  monthIndex: number;
  label: string;
  /** Dia acumulado do início da obra (ex.: 30, 60, 90…) — padrão planilha Caixa */
  periodDay: number;
  monthStartIso: string;
  monthEndIso: string;
}

export interface HistogramItemRow {
  itemKey: string;
  index: number;
  code: string;
  description: string;
  unit: string;
  monthlyValues: number[];
  total: number;
}

export interface HistogramSectionModel {
  title: string;
  category: ResourceCategory;
  columns: HistogramMonthColumn[];
  items: HistogramItemRow[];
  monthlyTotals: number[];
  /** Valores do gráfico (ex.: profissionais médios para MO em horas) */
  chartValues: number[];
  chartYLabel: string;
}

export interface HistogramWorkbookModel {
  sections: HistogramSectionModel[];
  hasSchedule: boolean;
  servicesWithCpu: number;
  projectLabel: string;
  clientLabel: string;
}

const HOURS_PER_WORKER_MONTH = 22 * 8;

export const HISTOGRAM_ITEM_COLORS = [
  "#0B2E4A",
  "#F59E0B",
  "#10B981",
  "#F472B6",
  "#A78BFA",
  "#FB7185",
  "#34D399",
  "#60A5FA",
  "#FBBF24",
  "#C084FC",
  "#2DD4BF",
  "#F97316",
] as const;

export function histogramItemColor(index: number): string {
  return HISTOGRAM_ITEM_COLORS[index % HISTOGRAM_ITEM_COLORS.length];
}

export interface HistogramReportModel {
  maoObra: HistogramSectionModel | null;
  equipamento: HistogramSectionModel | null;
  hasSchedule: boolean;
  servicesWithCpu: number;
  projectLabel: string;
  clientLabel: string;
}

const HISTOGRAM_SECTION_TITLES: Record<ResourceCategory, string> = {
  mao_obra: "HISTOGRAMA DE MÃO DE OBRA DIRETA",
  equipamento: "HISTOGRAMA DE EQUIPAMENTOS",
  insumo: "HISTOGRAMA DE INSUMOS",
};

export { HISTOGRAM_SECTION_TITLES };

function parseDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
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

function serviceValue(row: BudgetRow): number {
  return Math.max(0, row.total_effective ?? row.total_price ?? 0);
}

function classifyAbc(cumulativePct: number): AbcClass {
  if (cumulativePct <= 80) return "A";
  if (cumulativePct <= 95) return "B";
  return "C";
}

export function buildAbcCurve(rows: BudgetRow[]): AbcItem[] {
  const services = rows.filter((r) => r.row_type === "S" && !r.is_memory_row);
  const sorted = [...services].sort((a, b) => serviceValue(b) - serviceValue(a));
  const total = sorted.reduce((sum, r) => sum + serviceValue(r), 0) || 1;

  let cumulative = 0;
  return sorted.map((row) => {
    const value = serviceValue(row);
    const pct = (value / total) * 100;
    cumulative += pct;
    return {
      row_id: row.row_id,
      code: row.code,
      name: row.name,
      value,
      pct,
      cumulativePct: cumulative,
      abcClass: classifyAbc(cumulative),
    };
  });
}

export interface ScurvePoint {
  label: string;
  physicalMonthlyPct: number;
  physicalCumulativePct: number;
  financialMonthly: number;
  financialCumulative: number;
  financialCumulativePct: number;
}

export function buildScurvePoints(
  schedule: ProjectSchedule | undefined | null,
  rows: BudgetRow[]
): { points: ScurvePoint[]; totalFinancial: number; hasSchedule: boolean } {
  if (!schedule?.project_start || !schedule.tasks?.length) {
    return { points: [], totalFinancial: 0, hasSchedule: false };
  }

  const { months, totalFinancial } = buildScheduleCurvesByMonth(schedule, rows);
  const finDenom = totalFinancial > 0 ? totalFinancial : 1;

  const points: ScurvePoint[] = months.map((m: MonthBucket) => ({
    label: m.label,
    physicalMonthlyPct: m.physicalMonthlyPct,
    physicalCumulativePct: m.physicalCumulativePct,
    financialMonthly: m.financialMonthly,
    financialCumulative: m.financialCumulative,
    financialCumulativePct: (m.financialCumulative / finDenom) * 100,
  }));

  return { points, totalFinancial, hasSchedule: points.length > 0 };
}

function itemQuantityForService(item: OpenCompositionItem, serviceQty: number): number {
  return Math.max(0, item.coefficient * Math.max(0, serviceQty));
}

function isHourUnit(unit: string): boolean {
  const u = unit.trim().toUpperCase();
  return u === "H" || u === "HH" || u === "CH" || u === "H/H" || u.includes("HORA");
}

function histogramItemKey(item: OpenCompositionItem): string {
  return `${item.code}|${item.description}|${item.unit}`;
}

function toChartContribution(
  category: ResourceCategory,
  value: number,
  unit: string
): number {
  if (category === "mao_obra" && isHourUnit(unit)) {
    return value / HOURS_PER_WORKER_MONTH;
  }
  return value;
}

function buildMonthColumns(
  schedule: ProjectSchedule,
  scheduleMonths: MonthBucket[]
): HistogramMonthColumn[] {
  const projectStart = schedule.project_start;
  return scheduleMonths.map((m) => ({
    monthIndex: m.monthIndex,
    label: m.label,
    periodDay: daysBetween(projectStart, m.monthEndIso) + 1,
    monthStartIso: m.monthStartIso,
    monthEndIso: m.monthEndIso,
  }));
}

function buildHistogramSection(
  category: ResourceCategory,
  columns: HistogramMonthColumn[],
  rows: BudgetRow[],
  schedule: ProjectSchedule,
  compositions: Map<string, OpenCompositionDetail>,
  scheduleMonths: MonthBucket[]
): { items: HistogramItemRow[]; servicesWithCpu: number } {
  const monthCount = columns.length;
  const accum = new Map<
    string,
    { code: string; description: string; unit: string; monthly: number[] }
  >();
  let servicesWithCpu = 0;

  const services = rows.filter((r) => r.row_type === "S" && !r.is_memory_row);

  for (const service of services) {
    const detail = compositions.get(service.row_id);
    if (!detail) continue;
    servicesWithCpu += 1;

    const task = taskForService(schedule, service.row_id);
    const serviceQty = service.quantity ?? 1;

    for (const item of detail.items) {
      const cat = resolveResourceCategory(item);
      if (cat !== category) continue;
      if (category === "mao_obra" && !isHistogramDirectLabor(item)) continue;

      const totalQty = itemQuantityForService(item, serviceQty);
      if (totalQty <= 0) continue;

      const key = histogramItemKey(item);
      let row = accum.get(key);
      if (!row) {
        row = {
          code: item.code,
          description: item.description,
          unit: item.unit,
          monthly: new Array(monthCount).fill(0),
        };
        accum.set(key, row);
      }

      const addMonthly = (index: number, rawQty: number) => {
        row!.monthly[index] =
          (row!.monthly[index] ?? 0) + toChartContribution(category, rawQty, item.unit);
      };

      if (!task?.early_start || !task.early_finish) {
        addMonthly(0, totalQty);
        continue;
      }

      const duration = Math.max(1, task.duration_days);
      for (let i = 0; i < monthCount; i++) {
        const m = scheduleMonths[i];
        if (!m) continue;
        const overlap = overlapDays(
          task.early_start,
          task.early_finish,
          m.monthStartIso,
          m.monthEndIso
        );
        if (overlap <= 0) continue;
        addMonthly(i, totalQty * (overlap / duration));
      }
    }
  }

  const items: HistogramItemRow[] = [...accum.entries()]
    .map(([itemKey, row]) => ({
      itemKey,
      index: 0,
      code: row.code,
      description: row.description,
      unit: row.unit,
      monthlyValues: row.monthly,
      total: row.monthly.reduce((s, v) => s + v, 0),
    }))
    .filter((r) => r.total > 0.0001)
    .sort((a, b) => b.total - a.total)
    .map((r, i) => ({ ...r, index: i + 1 }));

  return { items, servicesWithCpu };
}

export interface StackedHistogramModel {
  months: StackedHistogramMonth[];
  hasSchedule: boolean;
  servicesWithCpu: number;
  projectLabel: string;
  clientLabel: string;
  totals: {
    equipamento: HistogramMeasure;
    mao_obra: HistogramMeasure;
  };
}

const EMPTY_MEASURE: HistogramMeasure = { quantity: 0, value: 0 };

function histogramQuantityForItem(
  item: OpenCompositionItem,
  serviceQty: number,
  category: ResourceCategory
): number {
  const qty = itemQuantityForService(item, serviceQty);
  if (category === "mao_obra" && isHourUnit(item.unit)) {
    return qty / HOURS_PER_WORKER_MONTH;
  }
  return qty;
}

export function buildStackedHistogram(
  schedule: ProjectSchedule | undefined | null,
  rows: BudgetRow[],
  compositions: Map<string, OpenCompositionDetail>,
  priceMode: "comd" | "semd" = "comd",
  project?: { projeto?: string; empresa?: string; orgao?: string; objeto?: string }
): StackedHistogramModel {
  const clientLabel = project?.empresa?.trim() || project?.orgao?.trim() || "—";
  const projectLabel = [project?.projeto, project?.objeto].filter(Boolean).join(" — ") || "Obra";

  const { months, hasSchedule, servicesWithCpu } = buildMoEquipHistogram(
    schedule,
    rows,
    compositions,
    priceMode
  );

  if (!hasSchedule || !schedule?.project_start) {
    return {
      months: [],
      hasSchedule: false,
      servicesWithCpu: 0,
      projectLabel,
      clientLabel,
      totals: { equipamento: { ...EMPTY_MEASURE }, mao_obra: { ...EMPTY_MEASURE } },
    };
  }

  const { months: scheduleMonths } = buildScheduleCurvesByMonth(schedule, rows);
  const columns = buildMonthColumns(schedule, scheduleMonths);

  const stackedMonths: StackedHistogramMonth[] = months.map((m, i) => ({
    monthIndex: m.monthIndex,
    label: m.label,
    periodDay: columns[i]?.periodDay ?? (i + 1) * 30,
    equipamento: { quantity: m.equipamentoQty, value: m.equipamentoValue },
    mao_obra: { quantity: m.maoObraQty, value: m.maoObraValue },
  }));

  const totals = stackedMonths.reduce(
    (acc, m) => ({
      equipamento: {
        quantity: acc.equipamento.quantity + m.equipamento.quantity,
        value: acc.equipamento.value + m.equipamento.value,
      },
      mao_obra: {
        quantity: acc.mao_obra.quantity + m.mao_obra.quantity,
        value: acc.mao_obra.value + m.mao_obra.value,
      },
    }),
    {
      equipamento: { quantity: 0, value: 0 },
      mao_obra: { quantity: 0, value: 0 },
    }
  );

  return {
    months: stackedMonths,
    hasSchedule: true,
    servicesWithCpu,
    projectLabel,
    clientLabel,
    totals,
  };
}

function finalizeHistogramSection(
  category: ResourceCategory,
  columns: HistogramMonthColumn[],
  items: HistogramItemRow[]
): HistogramSectionModel {
  const monthlyTotals = columns.map((_, i) =>
    items.reduce((sum, item) => sum + (item.monthlyValues[i] ?? 0), 0)
  );

  const chartYLabel =
    category === "mao_obra" ? "Profissionais" : "Quantidade";

  return {
    title: HISTOGRAM_SECTION_TITLES[category],
    category,
    columns,
    items,
    monthlyTotals,
    chartValues: monthlyTotals,
    chartYLabel,
  };
}

export function buildHistogramItemStacks(section: HistogramSectionModel): {
  key: string;
  label: string;
  color: string;
  values: number[];
}[] {
  return section.items.map((item) => ({
    key: item.itemKey,
    label: item.description,
    color: histogramItemColor(item.index - 1),
    values: item.monthlyValues,
  }));
}

export function buildHistogramReport(
  schedule: ProjectSchedule | undefined | null,
  rows: BudgetRow[],
  compositions: Map<string, OpenCompositionDetail>,
  project?: { projeto?: string; empresa?: string; orgao?: string; objeto?: string }
): HistogramReportModel {
  const clientLabel = project?.empresa?.trim() || project?.orgao?.trim() || "—";
  const projectLabel =
    [project?.projeto, project?.objeto].filter(Boolean).join(" — ") || "Obra";

  if (!schedule?.project_start) {
    return {
      maoObra: null,
      equipamento: null,
      hasSchedule: false,
      servicesWithCpu: 0,
      projectLabel,
      clientLabel,
    };
  }

  const { months: scheduleMonths } = buildScheduleCurvesByMonth(schedule, rows);
  if (scheduleMonths.length === 0) {
    return {
      maoObra: null,
      equipamento: null,
      hasSchedule: false,
      servicesWithCpu: 0,
      projectLabel,
      clientLabel,
    };
  }

  const columns = buildMonthColumns(schedule, scheduleMonths);
  let servicesWithCpu = 0;

  const buildSection = (category: ResourceCategory): HistogramSectionModel | null => {
    const { items, servicesWithCpu: svc } = buildHistogramSection(
      category,
      columns,
      rows,
      schedule,
      compositions,
      scheduleMonths
    );
    servicesWithCpu = Math.max(servicesWithCpu, svc);
    if (items.length === 0) return null;
    return finalizeHistogramSection(category, columns, items);
  };

  return {
    maoObra: buildSection("mao_obra"),
    equipamento: buildSection("equipamento"),
    hasSchedule: true,
    servicesWithCpu,
    projectLabel,
    clientLabel,
  };
}

/** Planilha detalhada por categoria (MO + equipamentos). */
export function buildHistogramWorkbook(
  schedule: ProjectSchedule | undefined | null,
  rows: BudgetRow[],
  compositions: Map<string, OpenCompositionDetail>,
  project?: { projeto?: string; empresa?: string; orgao?: string; objeto?: string }
): HistogramWorkbookModel {
  const report = buildHistogramReport(schedule, rows, compositions, project);
  const sections = [report.maoObra, report.equipamento].filter(
    (s): s is HistogramSectionModel => s != null
  );
  return {
    sections,
    hasSchedule: report.hasSchedule,
    servicesWithCpu: report.servicesWithCpu,
    projectLabel: report.projectLabel,
    clientLabel: report.clientLabel,
  };
}

export function formatHistogramQty(value: number): string {
  if (Math.abs(value) < 0.0001) return "—";
  if (value >= 100) return value.toFixed(0);
  if (value >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

interface MoEquipMonthBucket {
  monthIndex: number;
  label: string;
  equipamentoQty: number;
  equipamentoValue: number;
  maoObraQty: number;
  maoObraValue: number;
}

/** Histograma MO + equipamentos: quantidades e valores mensais rateados pelo cronograma. */
export function buildMoEquipHistogram(
  schedule: ProjectSchedule | undefined | null,
  rows: BudgetRow[],
  compositions: Map<string, OpenCompositionDetail>,
  priceMode: "comd" | "semd" = "comd"
): { months: MoEquipMonthBucket[]; hasSchedule: boolean; servicesWithCpu: number } {
  if (!schedule?.project_start) {
    return { months: [], hasSchedule: false, servicesWithCpu: 0 };
  }

  const { months: scheduleMonths } = buildScheduleCurvesByMonth(schedule, rows);
  if (scheduleMonths.length === 0) {
    return { months: [], hasSchedule: false, servicesWithCpu: 0 };
  }

  const buckets: MoEquipMonthBucket[] = scheduleMonths.map((m) => ({
    monthIndex: m.monthIndex,
    label: m.label,
    equipamentoQty: 0,
    equipamentoValue: 0,
    maoObraQty: 0,
    maoObraValue: 0,
  }));

  const services = rows.filter((r) => r.row_type === "S" && !r.is_memory_row);
  let servicesWithCpu = 0;

  for (const service of services) {
    const detail = compositions.get(service.row_id);
    if (!detail) continue;
    servicesWithCpu += 1;

    const task = taskForService(schedule, service.row_id);
    const serviceQty = service.quantity ?? 1;

    for (const item of detail.items) {
      const cat = resolveResourceCategory(item);
      if (cat !== "mao_obra" && cat !== "equipamento") continue;

      const qty = histogramQuantityForItem(item, serviceQty, cat);
      const val = itemCostForService(item, serviceQty, priceMode);
      if (qty <= 0 && val <= 0) continue;

      const distribute = (factor: number, bucket: MoEquipMonthBucket) => {
        if (cat === "equipamento") {
          bucket.equipamentoQty += qty * factor;
          bucket.equipamentoValue += val * factor;
        } else {
          bucket.maoObraQty += qty * factor;
          bucket.maoObraValue += val * factor;
        }
      };

      if (!task?.early_start || !task.early_finish) {
        const first = buckets[0];
        if (first) distribute(1, first);
        continue;
      }

      const duration = Math.max(1, task.duration_days);
      for (let i = 0; i < buckets.length; i++) {
        const m = scheduleMonths[i];
        if (!m) continue;
        const overlap = overlapDays(
          task.early_start,
          task.early_finish,
          m.monthStartIso,
          m.monthEndIso
        );
        if (overlap <= 0) continue;
        distribute(overlap / duration, buckets[i]);
      }
    }
  }

  return { months: buckets, hasSchedule: true, servicesWithCpu };
}

/** @deprecated — use buildMoEquipHistogram */
export function buildResourceQuantityHistogram(
  schedule: ProjectSchedule | undefined | null,
  rows: BudgetRow[],
  compositions: Map<string, OpenCompositionDetail>
): { months: ResourceMonthBucket[]; hasSchedule: boolean; servicesWithCpu: number } {
  const { months, hasSchedule, servicesWithCpu } = buildMoEquipHistogram(
    schedule,
    rows,
    compositions,
    "comd"
  );
  return {
    months: months.map((m) => ({
      monthIndex: m.monthIndex,
      label: m.label,
      equipamento: m.equipamentoQty,
      insumo: 0,
      mao_obra: m.maoObraQty,
      total: m.equipamentoQty + m.maoObraQty,
      totalWithBdi: 0,
    })),
    hasSchedule,
    servicesWithCpu,
  };
}

/** @deprecated custos em R$ — use buildResourceQuantityHistogram */
export function buildResourceDemandHistogram(
  schedule: ProjectSchedule | undefined | null,
  rows: BudgetRow[],
  compositions: Map<string, OpenCompositionDetail>,
  priceMode: "comd" | "semd" = "comd"
): { months: ResourceMonthBucket[]; hasSchedule: boolean; servicesWithCpu: number } {
  if (!schedule?.project_start) {
    return { months: [], hasSchedule: false, servicesWithCpu: 0 };
  }

  const { months: scheduleMonths } = buildScheduleCurvesByMonth(schedule, rows);
  if (scheduleMonths.length === 0) {
    return { months: [], hasSchedule: false, servicesWithCpu: 0 };
  }

  const buckets: ResourceMonthBucket[] = scheduleMonths.map((m) => ({
    monthIndex: m.monthIndex,
    label: m.label,
    equipamento: 0,
    insumo: 0,
    mao_obra: 0,
    total: 0,
    totalWithBdi: 0,
  }));

  const services = rows.filter((r) => r.row_type === "S" && !r.is_memory_row);
  let servicesWithCpu = 0;

  for (const service of services) {
    const detail = compositions.get(service.row_id);
    if (!detail) continue;
    servicesWithCpu += 1;

    const task = taskForService(schedule, service.row_id);
    const categoryTotals = categoryTotalsFromComposition(
      detail,
      service.quantity ?? 1,
      priceMode
    );
    const categorySum =
      categoryTotals.equipamento + categoryTotals.insumo + categoryTotals.mao_obra;
    if (categorySum <= 0) continue;

    const bdiFactor = serviceBdiFactor(service, categorySum);

    if (!task?.early_start || !task.early_finish) {
      const first = buckets[0];
      if (first) {
        first.equipamento += categoryTotals.equipamento;
        first.insumo += categoryTotals.insumo;
        first.mao_obra += categoryTotals.mao_obra;
        first.total += categorySum;
        first.totalWithBdi += categorySum * bdiFactor;
      }
      continue;
    }

    const duration = Math.max(1, task.duration_days);

    for (let i = 0; i < buckets.length; i++) {
      const m = scheduleMonths[i];
      if (!m) continue;
      const overlap = overlapDays(
        task.early_start,
        task.early_finish,
        m.monthStartIso,
        m.monthEndIso
      );
      if (overlap <= 0) continue;
      const factor = overlap / duration;
      buckets[i].equipamento += categoryTotals.equipamento * factor;
      buckets[i].insumo += categoryTotals.insumo * factor;
      buckets[i].mao_obra += categoryTotals.mao_obra * factor;
      buckets[i].total += categorySum * factor;
      buckets[i].totalWithBdi += categorySum * factor * bdiFactor;
    }
  }

  return { months: buckets, hasSchedule: true, servicesWithCpu };
}

function itemCostForService(
  item: OpenCompositionItem,
  serviceQty: number,
  mode: "comd" | "semd"
): number {
  const unitPartial =
    mode === "semd" ? item.partial_cost_sem ?? item.partial_cost : item.partial_cost;
  return Math.max(0, unitPartial * Math.max(0, serviceQty));
}

function categoryTotalsFromComposition(
  detail: OpenCompositionDetail,
  serviceQty: number,
  mode: "comd" | "semd"
): Record<ResourceCategory, number> {
  const totals: Record<ResourceCategory, number> = {
    equipamento: 0,
    insumo: 0,
    mao_obra: 0,
  };
  let composicaoCost = 0;

  for (const item of detail.items) {
    const cat = resolveResourceCategory(item);
    const cost = itemCostForService(item, serviceQty, mode);
    if (cat) {
      totals[cat] += cost;
    } else if (item.item_type?.toLowerCase() === "composicao") {
      composicaoCost += cost;
    }
  }

  const directSum = totals.equipamento + totals.insumo + totals.mao_obra;
  if (composicaoCost > 0 && directSum > 0) {
    for (const cat of ["equipamento", "insumo", "mao_obra"] as ResourceCategory[]) {
      totals[cat] += composicaoCost * (totals[cat] / directSum);
    }
  } else if (composicaoCost > 0) {
    totals.insumo += composicaoCost;
  }

  return totals;
}

function taskForService(schedule: ProjectSchedule, rowId: string): ScheduleTask | undefined {
  return schedule.tasks.find(
    (t) => t.budget_row_id === rowId && !t.is_summary && t.early_start && t.early_finish
  );
}

/** Fator BDI por serviço: total efetivo ÷ custo analítico da CPU */
function serviceBdiFactor(service: BudgetRow, analyticalCost: number): number {
  const effective = serviceValue(service);
  if (analyticalCost > 0) return effective / analyticalCost;
  const unitBase = Math.max(0, (service.unit_cost ?? 0) * Math.max(0, service.quantity ?? 1));
  return unitBase > 0 ? effective / unitBase : 1;
}

export interface BudgetAnalyticsReconciliation {
  serviceCount: number;
  serviceTotalEffective: number;
  serviceTotalUnitCost: number;
  unscheduledServices: { code: string; name: string; value: number }[];
  unscheduledValue: number;
  scurveFinancialTotal: number;
  abcTotal: number;
}

export function reconcileBudgetAnalytics(
  schedule: ProjectSchedule | undefined | null,
  rows: BudgetRow[]
): BudgetAnalyticsReconciliation {
  const services = rows.filter((r) => r.row_type === "S" && !r.is_memory_row);
  const serviceTotalEffective = services.reduce((s, r) => s + serviceValue(r), 0);
  const serviceTotalUnitCost = services.reduce(
    (s, r) => s + Math.max(0, (r.unit_cost ?? 0) * Math.max(0, r.quantity ?? 1)),
    0
  );
  const abc = buildAbcCurve(rows);
  const abcTotal = abc.reduce((s, i) => s + i.value, 0);
  const { totalFinancial } = buildScurvePoints(schedule, rows);

  const unscheduledServices: BudgetAnalyticsReconciliation["unscheduledServices"] = [];
  if (schedule?.tasks?.length) {
    for (const service of services) {
      if (!taskForService(schedule, service.row_id)) {
        unscheduledServices.push({
          code: service.code,
          name: service.name,
          value: serviceValue(service),
        });
      }
    }
  }

  const unscheduledValue = unscheduledServices.reduce((s, u) => s + u.value, 0);

  return {
    serviceCount: services.length,
    serviceTotalEffective,
    serviceTotalUnitCost,
    unscheduledServices,
    unscheduledValue,
    scurveFinancialTotal: totalFinancial,
    abcTotal,
  };
}

export function formatQuantity(value: number, maxDecimals = 2): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 10_000) return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
  return value.toLocaleString("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxDecimals,
  });
}

export function formatBrlCompact(value: number): string {
  if (value >= 1_000_000) return `R$ ${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `R$ ${(value / 1_000).toFixed(0)}k`;
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

export function formatBrl(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
