"use client";

import { useState } from "react";
import Link from "next/link";
import ChatBox, { type ChatSendOptions } from "@/components/ChatBox";
import JsonViewer from "@/components/JsonViewer";
import LoadingSpinner from "@/components/LoadingSpinner";
import PipelineSteps, { type PipelineStep } from "@/components/PipelineSteps";
import ShellHeader from "@/components/ShellHeader";
import { useActivity } from "@/context/ActivityContext";
import { api } from "@/services/api";
import type { CopilotResponse } from "@/types/api";

export default function CopilotPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CopilotResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const { pushActivity, updateActivity } = useActivity();

  const handleSend = async (text: string, options: ChatSendOptions) => {
    setLoading(true);
    setError(null);
    setResult(null);

    const activityId = `copilot-${Date.now()}`;
    pushActivity({
      id: activityId,
      source: "copilot",
      message: "Copilot — planejando e executando…",
      status: "running",
      phase: "plan",
    });
    setSteps([
      { id: "intent", label: "Intent", status: "running" },
      { id: "plan", label: "Plano", status: "pending" },
      { id: "execute", label: "Execução", status: "pending" },
      { id: "evaluate", label: "Avaliação", status: "pending" },
    ]);

    try {
      const response = await api.copilot({
        text,
        use_rag: options.useRag,
        persist: options.persist,
      });
      setResult(response);
      setSteps([
        { id: "intent", label: "Intent", status: "done" },
        { id: "plan", label: "Plano", status: "done" },
        { id: "execute", label: "Execução", status: "done" },
        { id: "evaluate", label: "Avaliação", status: "done" },
      ]);
      updateActivity(activityId, {
        status: "done",
        message: `Copilot concluído — ${response.disciplines.length} disciplina(s)`,
        phase: "evaluate",
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro no Copilot";
      setError(msg);
      setSteps((prev) =>
        prev.map((s) => (s.status === "running" ? { ...s, status: "error" } : s))
      );
      updateActivity(activityId, { status: "error", message: msg });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <ShellHeader className="px-6" showModelsStatus>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Copilot v1</h1>
          <p className="text-sm text-slate-500">
            Planejamento → multi-agente → síntese → avaliação de qualidade
          </p>
        </div>
        <Link href="/orchestrate" className="text-xs text-slate-500 hover:text-brand-300">
          Orquestrador →
        </Link>
      </ShellHeader>

      <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-6">
        <ChatBox onSend={handleSend} disabled={loading} placeholder="Descreva o problema de engenharia…" />

        {loading && (
          <div className="flex items-center gap-3 text-slate-400">
            <LoadingSpinner size="sm" />
            <span>Copilot em execução — pode levar alguns minutos…</span>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {steps.length > 0 && <PipelineSteps steps={steps} />}

        {result && (
          <div className="space-y-4">
            <div className="app-card p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Intent</p>
              <p className="mt-1 text-white">
                {result.intent}{" "}
                <span className="text-slate-500">
                  ({Math.round(result.intent_confidence * 100)}%)
                </span>
              </p>
              {result.disciplines.length > 0 && (
                <p className="mt-2 text-sm text-slate-400">
                  Disciplinas: {result.disciplines.join(", ")}
                </p>
              )}
            </div>
            {result.evaluation_v2 && (
              <div className="app-card p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Evaluation v2</p>
                <p className="mt-1 text-brand-300">
                  Nota {(result.evaluation_v2 as { final_score?: number }).final_score?.toFixed(2)}{" "}
                  — {(result.evaluation_v2 as { grade?: string }).grade}
                </p>
              </div>
            )}
            <JsonViewer data={result} title="Resposta completa" defaultExpanded={false} />
          </div>
        )}
      </div>
    </>
  );
}
