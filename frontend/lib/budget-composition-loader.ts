import { api } from "@/services/api";
import type { OpenCompositionDetail } from "@/types/api";
import {
  compositionFetchKey,
  getCachedComposition,
  setCachedComposition,
  type CachedCompositionEntry,
} from "@/lib/budget-analitico-cache";
import {
  type ServiceCompositionBundle,
  setServiceCompositionBundle,
} from "@/lib/budget-histogram-cache";
import {
  extractBudgetAnaliticoLines,
  isSeminfCompositionCode,
  type BudgetAnaliticoLine,
  type ResolvePriceBaseOptions,
} from "@/lib/budget-analitico";

export function buildCompositionLoadKey(lines: BudgetAnaliticoLine[]): string {
  return lines
    .map(
      (l) =>
        `${l.row_id}:${l.composition_code}:${l.base?.reference ?? ""}:${l.base?.uf ?? ""}`
    )
    .join("|");
}

export interface CompositionLoadProgress {
  compositions: Map<string, OpenCompositionDetail>;
  done: number;
  total: number;
  errorCount: number;
  loading: boolean;
}

/**
 * Carrega CPUs dos serviços — usa cache global de composição + bundle por sessão.
 * Idempotente: chamadas concorrentes com o mesmo bundleKey compartilham a mesma promise.
 */
const inflightByBundleKey = new Map<string, Promise<ServiceCompositionBundle>>();

export function loadBudgetServiceCompositions(
  lines: BudgetAnaliticoLine[],
  bundleKey: string,
  loadKey: string,
  options?: { onProgress?: (p: CompositionLoadProgress) => void }
): Promise<ServiceCompositionBundle> {
  const existing = inflightByBundleKey.get(bundleKey);
  if (existing) return existing;

  const promise = (async (): Promise<ServiceCompositionBundle> => {
    const total = lines.length;
    const next = new Map<string, OpenCompositionDetail>();
    const pendingFetchKeys = new Set<string>();
    const rowIdsByFetchKey = new Map<string, string[]>();
    let errors = 0;

    const emit = (loading: boolean) => {
      options?.onProgress?.({
        compositions: new Map(next),
        done: next.size,
        total,
        errorCount: errors,
        loading,
      });
    };

    for (const line of lines) {
      if (!line.base?.reference) {
        errors += 1;
        continue;
      }
      const fetchKey = compositionFetchKey(
        line.composition_code,
        line.base.reference,
        line.base.uf
      );
      const cached = getCachedComposition(fetchKey);
      if (cached?.status === "loaded") {
        next.set(line.row_id, cached.detail);
      } else if (cached?.status === "error") {
        errors += 1;
      } else {
        pendingFetchKeys.add(fetchKey);
        const list = rowIdsByFetchKey.get(fetchKey) ?? [];
        list.push(line.row_id);
        rowIdsByFetchKey.set(fetchKey, list);
      }
    }

    emit(pendingFetchKeys.size > 0);

    if (pendingFetchKeys.size === 0) {
      const bundle: ServiceCompositionBundle = {
        compositions: new Map(next),
        errorCount: errors,
        progressDone: next.size,
        progressTotal: total,
        loading: false,
        loadKey,
        updatedAt: Date.now(),
      };
      setServiceCompositionBundle(bundleKey, bundle);
      return bundle;
    }

    for (const fetchKey of Array.from(pendingFetchKeys)) {
      const sampleLine = lines.find((l) => {
        if (!l.base?.reference) return false;
        return (
          compositionFetchKey(l.composition_code, l.base.reference, l.base.uf) === fetchKey
        );
      });
      if (!sampleLine?.base?.reference) continue;

      try {
        const detail = await api.pricingSyncOpenComposition(sampleLine.composition_code, {
          uf: sampleLine.base.uf,
          reference: sampleLine.base.reference,
        });
        const entry: CachedCompositionEntry = { status: "loaded", detail };
        setCachedComposition(fetchKey, entry);
        for (const rowId of rowIdsByFetchKey.get(fetchKey) ?? []) {
          next.set(rowId, detail);
        }
      } catch {
        const msg = isSeminfCompositionCode(sampleLine.composition_code)
          ? "Base DP/SEMINF não encontrada"
          : `CPU não encontrada (${sampleLine.composition_code})`;
        setCachedComposition(fetchKey, { status: "error", message: msg });
        errors += rowIdsByFetchKey.get(fetchKey)?.length ?? 1;
      }

      emit(true);
    }

    const bundle: ServiceCompositionBundle = {
      compositions: new Map(next),
      errorCount: errors,
      progressDone: next.size,
      progressTotal: total,
      loading: false,
      loadKey,
      updatedAt: Date.now(),
    };
    setServiceCompositionBundle(bundleKey, bundle);
    emit(false);
    return bundle;
  })().finally(() => {
    inflightByBundleKey.delete(bundleKey);
  });

  inflightByBundleKey.set(bundleKey, promise);
  return promise;
}

export function extractCompositionLines(
  rows: import("@/types/api").BudgetRow[],
  priceBases: import("@/types/api").BudgetPriceBaseSelection[],
  resolveOptions: ResolvePriceBaseOptions
): BudgetAnaliticoLine[] {
  return extractBudgetAnaliticoLines(rows, priceBases, resolveOptions);
}
