import type { OpenCompositionDetail } from "@/types/api";
import { invalidateAllHistogramCaches } from "@/lib/budget-histogram-cache";

export type CachedCompositionEntry =
  | { status: "loaded"; detail: OpenCompositionDetail }
  | { status: "error"; message: string };

export interface AnaliticoTabUiState {
  filterText: string;
  priceMode: "comd" | "semd";
}

const compositionCache = new Map<string, CachedCompositionEntry>();
const uiStateBySession = new Map<string, AnaliticoTabUiState>();
let bankReferencesCache: import("@/types/api").PriceBankReference[] | null = null;
let bankReferencesPromise: Promise<import("@/types/api").PriceBankReference[]> | null = null;

export function compositionFetchKey(
  code: string,
  reference: string,
  uf: string
): string {
  return `${code.trim()}|${reference.trim()}|${uf.trim().toUpperCase()}`;
}

export function getCachedComposition(key: string): CachedCompositionEntry | undefined {
  return compositionCache.get(key);
}

export function setCachedComposition(key: string, entry: CachedCompositionEntry): void {
  compositionCache.set(key, entry);
}

export function getAnaliticoUiState(sessionId: string): AnaliticoTabUiState | undefined {
  return uiStateBySession.get(sessionId);
}

export function setAnaliticoUiState(sessionId: string, state: AnaliticoTabUiState): void {
  uiStateBySession.set(sessionId, state);
}

export function clearAnaliticoUiState(sessionId: string): void {
  uiStateBySession.delete(sessionId);
}

/** Remove entradas de CPU ligadas a um período (após reimport de base). */
export function invalidateCompositionReference(reference: string): void {
  const ref = reference.trim();
  for (const key of compositionCache.keys()) {
    if (key.includes(`|${ref}|`)) {
      compositionCache.delete(key);
    }
  }
  // Bundles/modelo do histograma dependem das CPUs — limpar cache derivado
  invalidateAllHistogramCaches();
}

export async function loadBankReferencesCached(
  fetcher: () => Promise<import("@/types/api").PriceBankReference[]>
): Promise<import("@/types/api").PriceBankReference[]> {
  if (bankReferencesCache) return bankReferencesCache;
  if (!bankReferencesPromise) {
    bankReferencesPromise = fetcher()
      .then((refs) => {
        bankReferencesCache = refs;
        return refs;
      })
      .catch((err) => {
        bankReferencesPromise = null;
        throw err;
      });
  }
  return bankReferencesPromise;
}

export function resetBankReferencesCache(): void {
  bankReferencesCache = null;
  bankReferencesPromise = null;
}

const MAX_CONCURRENT_COMPOSITION_FETCHES = 4;
let activeCompositionFetches = 0;
const compositionFetchWaitQueue: Array<() => void> = [];
const inflightCompositionFetches = new Map<string, Promise<OpenCompositionDetail>>();

function acquireCompositionFetchSlot(): Promise<void> {
  if (activeCompositionFetches < MAX_CONCURRENT_COMPOSITION_FETCHES) {
    activeCompositionFetches += 1;
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    compositionFetchWaitQueue.push(() => {
      activeCompositionFetches += 1;
      resolve();
    });
  });
}

function releaseCompositionFetchSlot(): void {
  activeCompositionFetches -= 1;
  const next = compositionFetchWaitQueue.shift();
  if (next) next();
}

/** Fila global + dedup in-flight — evita centenas de requests paralelos ao abrir orçamento. */
export async function fetchCompositionCached(
  code: string,
  reference: string,
  uf: string,
  fetcher: () => Promise<OpenCompositionDetail>
): Promise<OpenCompositionDetail> {
  const key = compositionFetchKey(code, reference, uf);
  const cached = getCachedComposition(key);
  if (cached?.status === "loaded") return cached.detail;

  const inflight = inflightCompositionFetches.get(key);
  if (inflight) return inflight;

  const promise = (async () => {
    await acquireCompositionFetchSlot();
    try {
      const again = getCachedComposition(key);
      if (again?.status === "loaded") return again.detail;

      const detail = await fetcher();
      setCachedComposition(key, { status: "loaded", detail });
      return detail;
    } catch (e) {
      const message = e instanceof Error ? e.message : "Erro ao carregar composição";
      setCachedComposition(key, { status: "error", message });
      throw e;
    } finally {
      releaseCompositionFetchSlot();
      inflightCompositionFetches.delete(key);
    }
  })();

  inflightCompositionFetches.set(key, promise);
  return promise;
}
