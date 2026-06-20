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
import type { OrchestrateResponse } from "@/types/api";

export default function OrchestratePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OrchestrateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const { pushActivity, updateActivity } = useActivity();

  const handleSend = async (text: string, options: ChatSendOptions) => {
    setLoading(true);
    setError(null);
    setResult(null);

    const activityId = `orch-${Date.now()}`;
    pushActivity({
      id: activityId,
      source: "orchestrator",
      message: "Decompondo problema multidisciplinar…",
      status: "running",
      phase: "decompose",
    });
    setSteps([
      { id: "decompose", label: "Decomposição", status: "running" },
      { id: "agents", label: "Agentes", status: "pending" },
      { id: "synthesis", label: "Síntese", status: "pending" },
    ]);

    try {
      const response = await api.orchestrate({
        text,
        use_rag: options.useRag,
        persist: options.persist,
        llm_model: options.llmModel !== "auto" ? options.llmModel : undefined,
      });
      setResult(response);
      setSteps([
        { id: "decompose", label: "Decomposição", status: "done" },
        ...response.disciplines.map((d) => ({
          id: `agent-${d}`,
          label: d,
          status: "done" as const,
        })),
        { id: "synthesis", label: "Síntese", status: "done" },
      ]);
      updateActivity(activityId, {
        status: "done",
        message: `Orquestração concluída (${response.disciplines.length} disciplinas)`,
        phase: "synthesis",
        discipline: response.disciplines[0],
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro na orquestração";
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
          <h1 className="text-lg font-semibold text-white">Orquestrador Multidisciplinar</h1>
          <p className="text-sm text-slate-500">
            Decomposição automática → múltiplos agentes → relatório unificado
          </p>
        </div>
      </ShellHeader>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {(loading || steps.length > 0) && (
          <div className="mx-auto mb-6 max-w-5xl">
            <PipelineSteps steps={steps} />
            <p className="mt-2 text-center text-xs text-slate-500">
              <Link href="/console" className="text-cyan-500 hover:text-cyan-400">
                Ver logs no Console
              </Link>
            </p>
          </div>
        )}

        {loading && (
          <div className="flex justify-center py-20">
            <LoadingSpinner label="Decompondo problema e executando agentes..." size="lg" />
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
            {error}
          </div>
        )}

        {result && !loading && (
          <div className="mx-auto max-w-5xl space-y-6">
            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Disciplinas detectadas
              </h2>
              <div className="flex flex-wrap gap-2">
                {result.disciplines.map((d) => (
                  <span
                    key={d}
                    className="rounded-full bg-cyan-500/10 px-3 py-1 text-sm font-medium text-cyan-300 ring-1 ring-cyan-500/30"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Resumo técnico
              </h2>
              <div className="rounded-xl bg-slate-800/50 p-4 text-sm leading-relaxed text-slate-200 ring-1 ring-slate-700/80">
                {result.synthesis.technical_summary}
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Resultados por disciplina
              </h2>
              <div className="space-y-4">
                {Object.entries(result.results).map(([discipline, agentResult]) => (
                  <div
                    key={discipline}
                    className="rounded-xl bg-slate-800/40 p-4 ring-1 ring-slate-700/60"
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <span className="font-medium text-cyan-300">{discipline}</span>
                      {agentResult.agent && (
                        <span className="text-xs text-slate-500">{agentResult.agent}</span>
                      )}
                    </div>
                    <p className="whitespace-pre-wrap text-sm text-slate-300">
                      {agentResult.result || agentResult.response}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Relatório final
              </h2>
              <div className="rounded-xl bg-slate-800/50 p-4 text-sm leading-relaxed text-slate-200 ring-1 ring-slate-700/80 whitespace-pre-wrap">
                {result.final_report}
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-slate-400">
                Resposta completa (JSON)
              </h2>
              <JsonViewer data={result} />
            </section>
          </div>
        )}

        {!result && !loading && !error && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <h2 className="text-xl font-semibold text-white">
              Análise multidisciplinar de engenharia
            </h2>
            <p className="mt-2 max-w-lg text-sm text-slate-400">
              Descreva um projeto complexo envolvendo várias disciplinas.
              Ex.: &quot;projeto de prédio residencial com estrutura e hidráulica&quot;
            </p>
          </div>
        )}
      </div>

      <ChatBox
        onSend={handleSend}
        loading={loading}
        placeholder="Descreva um problema multidisciplinar de engenharia..."
      />
    </>
  );
}
