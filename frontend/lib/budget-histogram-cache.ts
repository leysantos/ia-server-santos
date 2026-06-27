import type { StackedHistogramModel } from "@/lib/budget-analytics";
import type { OpenCompositionDetail, ProjectSchedule } from "@/types/api";

/** Estado carregado de CPUs por serviço — reutilizado entre aberturas da aba Histograma. */
export interface ServiceCompositionBundle {
  compositions: Map<string, OpenCompositionDetail>;
  errorCount: number;
  progressDone: number;
  progressTotal: number;
  loading: boolean;
  loadKey: string;
  updatedAt: number;
}

const bundleByKey = new Map<string, ServiceCompositionBundle>();
const histogramModelByKey = new Map<string, StackedHistogramModel>();

const MAX_BUNDLES = 12;
const MAX_MODELS = 24;

function trimMap<K, V>(map: Map<K, V>, max: number): void {
  while (map.size > max) {
    const first = map.keys().next().value;
    if (first === undefined) break;
    map.delete(first);
  }
}

export function serviceCompositionBundleKey(sessionId: string, loadKey: string): string {
  return `${sessionId}|${loadKey}`;
}

export function getServiceCompositionBundle(key: string): ServiceCompositionBundle | undefined {
  return bundleByKey.get(key);
}

export function setServiceCompositionBundle(key: string, bundle: ServiceCompositionBundle): void {
  bundleByKey.set(key, bundle);
  trimMap(bundleByKey, MAX_BUNDLES);
}

export function scheduleFingerprint(schedule: ProjectSchedule | undefined | null): string {
  if (!schedule?.project_start) return "";
  const tasks = (schedule.tasks ?? [])
    .map(
      (t) =>
        `${t.budget_row_id}:${t.early_start ?? ""}:${t.early_finish ?? ""}:${t.duration_days ?? ""}`
    )
    .sort()
    .join(";");
  return `${schedule.project_start}|${schedule.project_end ?? ""}|${tasks}`;
}

export function histogramModelCacheKey(
  sessionId: string,
  loadKey: string,
  priceMode: string,
  schedule: ProjectSchedule | undefined | null
): string {
  return `${sessionId}|${loadKey}|${priceMode}|${scheduleFingerprint(schedule)}`;
}

export function getCachedHistogramModel(key: string): StackedHistogramModel | undefined {
  return histogramModelByKey.get(key);
}

export function setCachedHistogramModel(key: string, model: StackedHistogramModel): void {
  histogramModelByKey.set(key, model);
  trimMap(histogramModelByKey, MAX_MODELS);
}

export function invalidateHistogramSession(sessionId: string): void {
  const prefix = `${sessionId}|`;
  for (const key of bundleByKey.keys()) {
    if (key.startsWith(prefix)) bundleByKey.delete(key);
  }
  for (const key of histogramModelByKey.keys()) {
    if (key.startsWith(prefix)) histogramModelByKey.delete(key);
  }
}

export function invalidateHistogramModelsForSession(sessionId: string): void {
  const prefix = `${sessionId}|`;
  for (const key of histogramModelByKey.keys()) {
    if (key.startsWith(prefix)) histogramModelByKey.delete(key);
  }
}

export function invalidateAllHistogramCaches(): void {
  bundleByKey.clear();
  histogramModelByKey.clear();
}
