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
import { api } from "@/services/api";
import type {
  VisionAnalysisItem,
  VisionAnalyzeProgress,
  VisionAnalyzeResponse,
} from "@/types/api";
import { useActivityOptional } from "@/context/ActivityContext";

export interface VisionJobState {
  projectId: string | null;
  projectName: string | null;
  analyzing: boolean;
  mode: string;
  progress: VisionAnalyzeProgress | null;
  partialItems: VisionAnalysisItem[];
  error: string | null;
  lastResult: VisionAnalyzeResponse | null;
  activityId: string | null;
}

const IDLE: VisionJobState = {
  projectId: null,
  projectName: null,
  analyzing: false,
  mode: "obra",
  progress: null,
  partialItems: [],
  error: null,
  lastResult: null,
  activityId: null,
};

interface StartVisionAnalysisOptions {
  projectId: string;
  projectName?: string;
  fileIds?: string[];
  mode?: string;
  extraContext?: string;
  skipTechnical?: boolean;
  /** Chamado quando um arquivo termina (atualiza lista na página se montada). */
  onFileDone?: (item: VisionAnalysisItem) => void;
  /** Chamado ao concluir com sucesso. */
  onComplete?: (result: VisionAnalyzeResponse) => void;
}

interface VisionJobContextValue extends VisionJobState {
  startAnalysis: (options: StartVisionAnalysisOptions) => void;
  dismissResult: () => void;
  refreshAnalyses: (projectId: string) => Promise<VisionAnalysisItem[]>;
}

const VisionJobContext = createContext<VisionJobContextValue | null>(null);

export function VisionJobProvider({ children }: { children: ReactNode }) {
  const [job, setJob] = useState<VisionJobState>(IDLE);
  const runningRef = useRef(false);
  const activity = useActivityOptional();

  const startAnalysis = useCallback(
    (options: StartVisionAnalysisOptions) => {
      if (runningRef.current) {
        return;
      }
      runningRef.current = true;

      const mode = options.mode ?? "obra";
      const totalGuess = options.fileIds?.length ?? 1;
      const liveId = `vision-${Date.now()}`;

      activity?.pushActivity({
        id: liveId,
        source: "vision",
        message: `Análise visual (${mode}) iniciada`,
        status: "running",
        phase: "prepare",
        projectId: options.projectId,
      });

      setJob({
        projectId: options.projectId,
        projectName: options.projectName ?? null,
        analyzing: true,
        mode,
        progress: {
          phase: "prepare",
          current: 0,
          total: totalGuess,
          percent: 0,
          message: "Iniciando análise…",
        },
        partialItems: [],
        error: null,
        lastResult: null,
        activityId: liveId,
      });

      // Sem AbortSignal — navegar no painel NÃO cancela o fetch.
      void (async () => {
        try {
          const result = await api.analyzeVisionWithProgress(
            options.projectId,
            {
              file_ids: options.fileIds,
              mode,
              extra_context: options.extraContext,
              skip_technical: options.skipTechnical ?? false,
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
            },
            (item) => {
              setJob((prev) => ({
                ...prev,
                partialItems: [
                  ...prev.partialItems.filter(
                    (a) => a.project_file_id !== item.project_file_id
                  ),
                  item,
                ],
              }));
              options.onFileDone?.(item);
            }
          );

          setJob((prev) => ({
            ...prev,
            analyzing: false,
            lastResult: result,
            partialItems: result.items,
            progress: {
              phase: "complete",
              current: result.total,
              total: result.total,
              percent: 100,
              message: "Análise concluída",
            },
            error: null,
          }));

          activity?.updateActivity(liveId, {
            status: "done",
            message: `Análise concluída: ${result.analyzed}/${result.total}`,
            phase: mode,
          });
          options.onComplete?.(result);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Falha na análise visual";
          setJob((prev) => ({
            ...prev,
            analyzing: false,
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
    [activity]
  );

  const dismissResult = useCallback(() => {
    setJob(IDLE);
  }, []);

  const refreshAnalyses = useCallback(async (projectId: string) => {
    const list = await api.listVisionAnalyses(projectId);
    return list.items;
  }, []);

  const value = useMemo(
    () => ({
      ...job,
      startAnalysis,
      dismissResult,
      refreshAnalyses,
    }),
    [job, startAnalysis, dismissResult, refreshAnalyses]
  );

  return <VisionJobContext.Provider value={value}>{children}</VisionJobContext.Provider>;
}

export function useVisionJob() {
  const ctx = useContext(VisionJobContext);
  if (!ctx) {
    throw new Error("useVisionJob must be used within VisionJobProvider");
  }
  return ctx;
}

export function useVisionJobOptional() {
  return useContext(VisionJobContext);
}
