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
import { knowledgeIngestNormsWithProgress } from "@/services/api";
import type { NormBulkIngestResponse, WebIngestProgress } from "@/types/api";
import { useActivityOptional } from "@/context/ActivityContext";
import { useSettingsKnowledgeOptional } from "@/contexts/SettingsKnowledgeContext";

export interface NormBulkImportOptions {
  force?: boolean;
  use_ai_fallback?: boolean;
  mark_edition_outdated?: boolean;
}

export interface NormBulkImportJobState {
  importing: boolean;
  fileCount: number;
  folderName: string | null;
  progress: WebIngestProgress | null;
  resultSummary: string | null;
  errors: { filename?: string; error?: string }[];
  error: string | null;
  lastReport: { filename: string; csv: string } | null;
  activityId: string | null;
}

const IDLE_JOB: NormBulkImportJobState = {
  importing: false,
  fileCount: 0,
  folderName: null,
  progress: null,
  resultSummary: null,
  errors: [],
  error: null,
  lastReport: null,
  activityId: null,
};

interface StartNormBulkImportParams {
  files: File[];
  folderName?: string | null;
  options: NormBulkImportOptions;
}

interface NormBulkImportContextValue extends NormBulkImportJobState {
  /** Arquivos selecionados (mantidos durante navegação). */
  selectedFiles: File[];
  setSelectedFiles: (files: File[]) => void;
  clearSelectedFiles: () => void;
  startImport: (params: StartNormBulkImportParams) => void;
  dismissResult: () => void;
  clearResult: () => void;
}

const NormBulkImportContext = createContext<NormBulkImportContextValue | null>(null);

export function NormBulkImportProvider({ children }: { children: ReactNode }) {
  const [selectedFiles, setSelectedFilesState] = useState<File[]>([]);
  const [job, setJob] = useState<NormBulkImportJobState>(IDLE_JOB);
  const runningRef = useRef(false);
  const filesRef = useRef<File[]>([]);
  const activity = useActivityOptional();
  const settingsKnowledge = useSettingsKnowledgeOptional();

  const setSelectedFiles = useCallback((files: File[]) => {
    setSelectedFilesState(files);
  }, []);

  const clearSelectedFiles = useCallback(() => {
    if (runningRef.current) return;
    setSelectedFilesState([]);
    filesRef.current = [];
  }, []);

  const dismissResult = useCallback(() => {
    if (runningRef.current) return;
    setJob(IDLE_JOB);
    setSelectedFilesState([]);
    filesRef.current = [];
  }, []);

  const clearResult = useCallback(() => {
    if (runningRef.current) return;
    setJob(IDLE_JOB);
  }, []);

  const startImport = useCallback(
    ({ files, folderName = null, options }: StartNormBulkImportParams) => {
      if (!files.length || runningRef.current) return;

      runningRef.current = true;
      filesRef.current = files;

      const liveId = `norm-bulk-${Date.now()}`;
      activity?.pushActivity({
        id: liveId,
        source: "upload",
        message: `Importação NBR/NR: ${files.length.toLocaleString("pt-BR")} PDF(s)`,
        status: "running",
        phase: "upload",
      });

      setJob({
        importing: true,
        fileCount: files.length,
        folderName,
        progress: {
          phase: "upload",
          current: 0,
          total: files.length,
          percent: 0,
          message: "Enviando PDFs…",
        },
        resultSummary: null,
        errors: [],
        error: null,
        lastReport: null,
        activityId: liveId,
      });

      // Sem AbortSignal — navegar no painel NÃO cancela o fetch.
      void (async () => {
        try {
          const res: NormBulkImportResponse = await knowledgeIngestNormsWithProgress(
            {
              files: filesRef.current,
              force: options.force,
              use_ai_fallback: options.use_ai_fallback,
              mark_edition_outdated: options.mark_edition_outdated,
              auto_index: true,
            },
            (progress) => {
              setJob((prev) => ({
                ...prev,
                progress,
              }));
              activity?.updateActivity(liveId, {
                message: `${progress.percent ?? 0}% · ${progress.message}`,
                phase: progress.phase,
              });
            }
          );

          let summary = `${res.ingested} norma(s) importada(s)`;
          if (res.skipped) summary += ` · ${res.skipped} ignorada(s) (duplicata)`;
          if (res.total_files) summary += ` · ${res.total_files} PDF(s) no lote`;

          setJob((prev) => ({
            ...prev,
            importing: false,
            resultSummary: summary,
            errors: (res.errors ?? []).map((e) => ({
              filename: e.filename ?? e.source,
              error: e.error,
            })),
            lastReport: res.report_csv
              ? {
                  csv: res.report_csv,
                  filename: res.report_filename ?? "auditoria-importacao-nbr.csv",
                }
              : null,
            error: null,
            progress: {
              phase: "complete",
              current: res.total_files ?? prev.fileCount,
              total: res.total_files ?? prev.fileCount,
              percent: 100,
              message: "Importação concluída",
            },
          }));

          activity?.updateActivity(liveId, {
            status: "done",
            message: summary,
            phase: "complete",
          });

          if (res.ingested > 0) {
            setSelectedFilesState([]);
            filesRef.current = [];
            await settingsKnowledge?.refresh();
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : "Erro na importação em lote";
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
      selectedFiles,
      setSelectedFiles,
      clearSelectedFiles,
      startImport,
      dismissResult,
      clearResult,
    }),
    [job, selectedFiles, setSelectedFiles, clearSelectedFiles, startImport, dismissResult, clearResult]
  );

  return (
    <NormBulkImportContext.Provider value={value}>{children}</NormBulkImportContext.Provider>
  );
}

export function useNormBulkImport() {
  const ctx = useContext(NormBulkImportContext);
  if (!ctx) {
    throw new Error("useNormBulkImport must be used within NormBulkImportProvider");
  }
  return ctx;
}

export function useNormBulkImportOptional() {
  return useContext(NormBulkImportContext);
}
