"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BudgetSessionResponse, OpenCompositionDetail } from "@/types/api";
import { loadBankReferencesCached } from "@/lib/budget-analitico-cache";
import {
  buildCompositionLoadKey,
  extractCompositionLines,
  loadBudgetServiceCompositions,
} from "@/lib/budget-composition-loader";
import {
  getServiceCompositionBundle,
  serviceCompositionBundleKey,
} from "@/lib/budget-histogram-cache";
import type { ResolvePriceBaseOptions } from "@/lib/budget-analitico";

export interface ServiceCompositionLoad {
  loaded: Map<string, OpenCompositionDetail>;
  loading: boolean;
  progress: { done: number; total: number };
  errorCount: number;
  loadKey: string;
}

function bundleToState(
  bundle: ReturnType<typeof getServiceCompositionBundle>,
  fallbackTotal: number
): Pick<ServiceCompositionLoad, "loaded" | "loading" | "progress" | "errorCount"> {
  if (!bundle) {
    return {
      loaded: new Map(),
      loading: false,
      progress: { done: 0, total: fallbackTotal },
      errorCount: 0,
    };
  }
  return {
    loaded: new Map(bundle.compositions),
    loading: bundle.loading,
    progress: { done: bundle.progressDone, total: bundle.progressTotal || fallbackTotal },
    errorCount: bundle.errorCount,
  };
}

export function useBudgetServiceCompositions(
  session: BudgetSessionResponse | null
): ServiceCompositionLoad {
  const rows = session?.rows ?? [];
  const priceBases = session?.project?.price_bases ?? [];
  const basePreco = session?.project?.base_preco;
  const sessionId = session?.session_id ?? "";

  const [bankReferences, setBankReferences] = useState<
    import("@/types/api").PriceBankReference[]
  >([]);
  const [compositions, setCompositions] = useState<Map<string, OpenCompositionDetail>>(
    new Map()
  );
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [errorCount, setErrorCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void loadBankReferencesCached(() =>
      api.pricingSyncBankReferences().then((r) => r.references ?? [])
    )
      .then((refs) => {
        if (!cancelled) setBankReferences(refs);
      })
      .catch(() => {
        if (!cancelled) setBankReferences([]);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const resolveOptions: ResolvePriceBaseOptions = useMemo(
    () => ({ bankReferences, basePreco }),
    [bankReferences, basePreco]
  );

  const lines = useMemo(
    () => extractCompositionLines(rows, priceBases, resolveOptions),
    [rows, priceBases, resolveOptions]
  );

  const loadKey = useMemo(() => buildCompositionLoadKey(lines), [lines]);
  const bundleKey = sessionId ? serviceCompositionBundleKey(sessionId, loadKey) : "";

  useEffect(() => {
    if (!sessionId || lines.length === 0) {
      setCompositions(new Map());
      setProgress({ done: 0, total: 0 });
      setLoading(false);
      setErrorCount(0);
      return;
    }

    let cancelled = false;
    const cached = getServiceCompositionBundle(bundleKey);

    if (cached && cached.loadKey === loadKey && !cached.loading) {
      const state = bundleToState(cached, lines.length);
      setCompositions(state.loaded);
      setProgress(state.progress);
      setErrorCount(state.errorCount);
      setLoading(false);
      return;
    }

    if (cached && cached.loadKey === loadKey && cached.loading) {
      const state = bundleToState(cached, lines.length);
      setCompositions(state.loaded);
      setProgress(state.progress);
      setErrorCount(state.errorCount);
      setLoading(true);
    }

    void loadBudgetServiceCompositions(lines, bundleKey, loadKey, {
      onProgress: (p) => {
        if (cancelled) return;
        setCompositions(new Map(p.compositions));
        setProgress({ done: p.done, total: p.total });
        setErrorCount(p.errorCount);
        setLoading(p.loading);
      },
    }).then((bundle) => {
      if (cancelled) return;
      setCompositions(new Map(bundle.compositions));
      setProgress({ done: bundle.progressDone, total: bundle.progressTotal });
      setErrorCount(bundle.errorCount);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [bundleKey, loadKey, lines, sessionId]);

  return { loaded: compositions, loading, progress, errorCount, loadKey };
}

/** Pré-carrega CPUs em background (ex.: ao abrir orçamento com cronograma). */
export async function prefetchBudgetServiceCompositions(
  session: BudgetSessionResponse
): Promise<void> {
  const sessionId = session.session_id;
  if (!sessionId) return;

  const refs = await loadBankReferencesCached(() =>
    api.pricingSyncBankReferences().then((r) => r.references ?? [])
  ).catch(() => [] as import("@/types/api").PriceBankReference[]);

  const lines = extractCompositionLines(
    session.rows ?? [],
    session.project?.price_bases ?? [],
    { bankReferences: refs, basePreco: session.project?.base_preco }
  );
  if (lines.length === 0) return;

  const loadKey = buildCompositionLoadKey(lines);
  const bundleKey = serviceCompositionBundleKey(sessionId, loadKey);
  const cached = getServiceCompositionBundle(bundleKey);
  if (cached && cached.loadKey === loadKey && !cached.loading) return;

  await loadBudgetServiceCompositions(lines, bundleKey, loadKey);
}
