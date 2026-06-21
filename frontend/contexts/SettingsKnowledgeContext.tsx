"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/services/api";
import type {
  KnowledgeCatalogResponse,
  KnowledgeOptionsResponse,
  KnowledgeStatsResponse,
} from "@/types/api";

interface IndexProgress {
  phase?: string | null;
  message?: string | null;
  percent?: number | null;
  current?: number | null;
  total?: number | null;
}

interface SettingsKnowledgeContextValue {
  options: KnowledgeOptionsResponse | null;
  stats: KnowledgeStatsResponse | null;
  catalog: KnowledgeCatalogResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  handleIndex: (base?: string, force?: boolean) => Promise<string>;
  indexing: string | null;
  indexProgress: IndexProgress | null;
  handleActivatePriceBase: (documentId: string) => Promise<void>;
  handleIndexBudgetModel: (documentId: string) => Promise<{ service_count: number; reason?: string }>;
  handleUpdateDocument: (
    documentId: string,
    payload: { name?: string; description?: string; content_type?: string; discipline?: string }
  ) => Promise<void>;
  handleDeleteDocument: (documentId: string) => Promise<void>;
}

const SettingsKnowledgeContext = createContext<SettingsKnowledgeContextValue | null>(null);

export function SettingsKnowledgeProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<KnowledgeOptionsResponse | null>(null);
  const [stats, setStats] = useState<KnowledgeStatsResponse | null>(null);
  const [catalog, setCatalog] = useState<KnowledgeCatalogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [indexing, setIndexing] = useState<string | null>(null);
  const [indexProgress, setIndexProgress] = useState<IndexProgress | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [optsRes, st] = await Promise.all([
        api.knowledgeOptions(),
        api.knowledgeStats(),
      ]);
      const catalogLimit = Math.min(
        20000,
        Math.max(5000, (st?.catalog_total ?? 0) + 100)
      );
      const cat = await api.knowledgeCatalog(catalogLimit);
      setOptions(optsRes);
      setStats(st);
      setCatalog(cat);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleIndex = useCallback(
    async (base?: string, force = false) => {
      const key = base ?? "all";
      setIndexing(key);
      setIndexProgress({ message: "Iniciando indexação…", percent: 0, current: 0, total: 0 });

      const poll = window.setInterval(async () => {
        try {
          const live = await api.consoleLive();
          const job =
            live.active_jobs.find((j) => j.kind === "knowledge" || j.kind === "norm_bulk") ??
            live.recent_jobs.find(
              (j) =>
                (j.kind === "knowledge" || j.kind === "norm_bulk") &&
                j.status === "running",
            );
          if (job) {
            setIndexProgress({
              phase: job.phase,
              message: job.message,
              percent: job.percent,
              current: job.current,
              total: job.total,
            });
          }
        } catch {
          /* ignore poll errors */
        }
      }, 2000);

      try {
        const result = await api.knowledgeIndex(base, force);
        await refresh();
        return base
          ? `Base ${base}: ${result.total_chunks} chunks indexados`
          : `Total: ${result.total_chunks} chunks no índice`;
      } finally {
        window.clearInterval(poll);
        setIndexing(null);
        setIndexProgress(null);
      }
    },
    [refresh]
  );

  const handleActivatePriceBase = useCallback(
    async (documentId: string) => {
      await api.knowledgeActivatePriceBase(documentId);
      await refresh();
    },
    [refresh]
  );

  const handleIndexBudgetModel = useCallback(
    async (documentId: string) => {
      const result = await api.knowledgeIndexBudgetModel(documentId);
      await refresh();
      return result;
    },
    [refresh]
  );

  const handleUpdateDocument = useCallback(
    async (
      documentId: string,
      payload: { name?: string; description?: string; content_type?: string; discipline?: string }
    ) => {
      await api.knowledgeUpdateDocument(documentId, payload);
      await refresh();
    },
    [refresh]
  );

  const handleDeleteDocument = useCallback(
    async (documentId: string) => {
      await api.knowledgeDeleteDocument(documentId);
      await refresh();
    },
    [refresh]
  );

  const value = useMemo(
    () => ({
      options,
      stats,
      catalog,
      loading,
      error,
      refresh,
      handleIndex,
      indexing,
      indexProgress,
      handleActivatePriceBase,
      handleIndexBudgetModel,
      handleUpdateDocument,
      handleDeleteDocument,
    }),
    [
      options,
      stats,
      catalog,
      loading,
      error,
      refresh,
      handleIndex,
      indexing,
      indexProgress,
      handleActivatePriceBase,
      handleIndexBudgetModel,
      handleUpdateDocument,
      handleDeleteDocument,
    ]
  );

  return (
    <SettingsKnowledgeContext.Provider value={value}>{children}</SettingsKnowledgeContext.Provider>
  );
}

export function useSettingsKnowledge() {
  const ctx = useContext(SettingsKnowledgeContext);
  if (!ctx) {
    throw new Error("useSettingsKnowledge must be used within SettingsKnowledgeProvider");
  }
  return ctx;
}

export function useSettingsKnowledgeOptional() {
  return useContext(SettingsKnowledgeContext);
}
