"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { knowledgeIngestWebWithProgress } from "@/services/api";
import type { WebIngestProgress } from "@/types/api";
import { useActivityOptional } from "@/context/ActivityContext";
import { useSettingsKnowledgeOptional } from "@/contexts/SettingsKnowledgeContext";

export interface KnowledgeWebImportOptions {
  page_url: string;
  discipline?: string;
  content_type?: string;
  force?: boolean;
  max_files?: number;
}

export interface KnowledgeWebImportJobState {
  importing: boolean;
  pageUrl: string | null;
  progress: WebIngestProgress | null;
  resultSummary: string | null;
  errors: { url?: string; error?: string; stage?: string }[];
  error: string | null;
  activityId: string | null;
}

const IDLE_JOB: KnowledgeWebImportJobState = {
  importing: false,
  pageUrl: null,
  progress: null,
  resultSummary: null,
  errors: [],
  error: null,
  activityId: null,
};

interface StartKnowledgeWebImportParams extends KnowledgeWebImportOptions {}

interface KnowledgeWebImportContextValue extends KnowledgeWebImportJobState {
  startImport: (params: StartKnowledgeWebImportParams) => void;
  dismissResult: () => void;
  clearResult: () => void;
}

const KnowledgeWebImportContext = createContext<KnowledgeWebImportContextValue | null>(null);

export function KnowledgeWebImportProvider({ children }: { children: ReactNode }) {
  const [job, setJob] = useState<KnowledgeWebImportJobState>(IDLE_JOB);
  const runningRef = useRef(false);
  const activity = useActivityOptional();
  const settingsKnowledge = useSettingsKnowledgeOptional();

  const dismissResult = useCallback(() => {
    if (runningRef.current) return;
    setJob(IDLE_JOB);
  }, []);

  const clearResult = useCallback(() => {
    if (runningRef.current) return;
    setJob(IDLE_JOB);
  }, []);

  const startImport = useCallback(
    ({ page_url, discipline, content_type, force, max_files = 200 }: StartKnowledgeWebImportParams) => {
      const url = page_url.trim();
      if (!url || runningRef.current) return;

      runningRef.current = true;
      const liveId = `knowledge-web-${Date.now()}`;
      const shortUrl = url.length > 56 ? `${url.slice(0, 55)}…` : url;

      activity?.pushActivity({
        id: liveId,
        source: "upload",
        message: `Importação web: ${shortUrl}`,
        status: "running",
        phase: "parse",
      });

      setJob({
        importing: true,
        pageUrl: url,
        progress: {
          phase: "parse",
          current: 0,
          total: 1,
          percent: 0,
          message: "Iniciando importação…",
        },
        resultSummary: null,
        errors: [],
        error: null,
        activityId: liveId,
      });

      // Sem AbortSignal — navegar para /console ou outra rota NÃO cancela o fetch.
      void (async () => {
        try {
          const res = await knowledgeIngestWebWithProgress(
            {
              page_url: url,
              discipline,
              content_type,
              force,
              max_files,
              auto_index: true,
            },
            (progress) => {
              setJob((prev) => ({
                ...prev,
                progress,
              }));
              activity?.updateActivity(liveId, {
                message: `${progress.percent ?? 0}% · ${progress.message ?? progress.phase ?? ""}`,
                phase: progress.phase,
              });
            }
          );

          const ok = res.ingested > 0 || res.downloaded > 0;
          const skipped = res.skipped ?? 0;
          let summary = `${res.ingested} documento(s) importado(s) · ${res.downloaded} baixado(s) · ${res.discovered} link(s)`;
          if (res.pages_fetched && res.pages_fetched > 1) {
            summary += ` · ${res.pages_fetched} página(s)`;
          }
          if (skipped > 0) {
            summary += ` · ${skipped} ignorado(s)`;
          }

          setJob((prev) => ({
            ...prev,
            importing: false,
            resultSummary: summary,
            errors: res.errors ?? [],
            error: ok || !res.errors?.length ? null : res.errors[0]?.error ?? "Falha na importação",
            progress: {
              phase: "done",
              current: 1,
              total: 1,
              percent: 100,
              message: "Importação concluída",
            },
          }));

          activity?.updateActivity(liveId, {
            status: ok ? "done" : "error",
            message: summary,
            phase: "complete",
          });

          if (ok) {
            await settingsKnowledge?.refresh();
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : "Erro na importação web";
          setJob((prev) => ({
            ...prev,
            importing: false,
            error: message,
            progress: null,
          }));
          activity?.updateActivity(liveId, {
            status: "error",
            message,
          });
        } finally {
          runningRef.current = false;
        }
      })();
    },
    [activity, settingsKnowledge]
  );

  const value = useMemo(
    () => ({
      ...job,
      startImport,
      dismissResult,
      clearResult,
    }),
    [job, startImport, dismissResult, clearResult]
  );

  return (
    <KnowledgeWebImportContext.Provider value={value}>
      {children}
    </KnowledgeWebImportContext.Provider>
  );
}

export function useKnowledgeWebImport() {
  const ctx = useContext(KnowledgeWebImportContext);
  if (!ctx) {
    throw new Error("useKnowledgeWebImport must be used within KnowledgeWebImportProvider");
  }
  return ctx;
}

export function useKnowledgeWebImportOptional() {
  return useContext(KnowledgeWebImportContext);
}
