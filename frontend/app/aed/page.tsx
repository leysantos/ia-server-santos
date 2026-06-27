"use client";

import { useState } from "react";
import Link from "next/link";
import ChatBox, { type ChatSendOptions } from "@/components/ChatBox";
import JsonViewer from "@/components/JsonViewer";
import LoadingSpinner from "@/components/LoadingSpinner";
import PipelineSteps, { type PipelineStep } from "@/components/PipelineSteps";
import ShellHeader from "@/components/ShellHeader";
import { useActivity } from "@/context/ActivityContext";
import { markdownToHtml } from "@/lib/markdown-lite";
import { api } from "@/services/api";
import type { AedResponse } from "@/types/api";

function reportMarkdown(result: AedResponse): string | null {
  const report = result.report as { final_report?: string } | undefined;
  if (typeof report?.final_report === "string" && report.final_report.trim()) {
    return report.final_report;
  }
  return null;
}

export default function AedPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [showRawJson, setShowRawJson] = useState(false);
  const { pushActivity, updateActivity } = useActivity();

  const handleSend = async (text: string, options: ChatSendOptions) => {
    setLoading(true);
    setError(null);
    setResult(null);

    const activityId = `aed-${Date.now()}`;
    pushActivity({
      id: activityId,
      source: "aed",
      message: "AED — análise e design autônomo…",
      status: "running",
      phase: "understanding",
    });
    setSteps([
      { id: "understanding", label: "Entendimento", status: "running" },
      { id: "designs", label: "Alternativas", status: "pending" },
      { id: "simulation", label: "Simulação", status: "pending" },
      { id: "selection", label: "Seleção", status: "pending" },
    ]);

    try {
      const response = await api.aed({
        text,
        use_rag: options.useRag,
        persist: options.persist,
      });
      setResult(response);
      setSteps([
        { id: "understanding", label: "Entendimento", status: "done" },
        { id: "designs", label: "Alternativas", status: "done" },
        { id: "simulation", label: "Simulação", status: "done" },
        { id: "selection", label: "Seleção", status: "done" },
      ]);
      updateActivity(activityId, {
        status: "done",
        message: "AED concluído — relatório gerado",
        phase: "selection",
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro no AED";
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
          <h1 className="text-lg font-semibold text-white">AED — Autonomous Engineering Designer</h1>
          <p className="text-sm text-slate-500">
            Entendimento → alternativas → simulação → comparação → seleção → relatório
          </p>
        </div>
        <Link href="/copilot" className="text-xs text-slate-500 hover:text-brand-300">
          Copilot →
        </Link>
      </ShellHeader>

      <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-6">
        <ChatBox
          onSend={handleSend}
          disabled={loading}
          placeholder="Ex.: dimensionar laje maciça 6×8 m, carga 3 kN/m², fck 30 MPa…"
        />

        {loading && (
          <div className="flex items-center gap-3 text-slate-400">
            <LoadingSpinner size="sm" />
            <span>AED em execução — pipeline completo pode levar vários minutos…</span>
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
            {(() => {
              const selection = result.selection as {
                name?: string;
                discipline?: string;
                justification?: string;
                final_selection_score?: number;
              };
              const finalReport = reportMarkdown(result);
              return (
                <>
                  <div className="app-card p-4">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Solução selecionada</p>
                    <p className="mt-1 text-lg font-medium text-white">
                      {selection.name || "—"}
                      {selection.discipline && (
                        <span className="ml-2 text-sm font-normal text-cyan-400/90">
                          [{selection.discipline}]
                        </span>
                      )}
                    </p>
                    {selection.justification && (
                      <p className="mt-2 text-sm leading-relaxed text-slate-300">{selection.justification}</p>
                    )}
                    {typeof selection.final_selection_score === "number" && (
                      <p className="mt-2 text-xs text-slate-500">
                        Score final: {selection.final_selection_score.toFixed(3)}
                      </p>
                    )}
                    {result.aed_run_id && (
                      <p className="mt-2 text-xs text-slate-500">
                        Salvo no histórico — Run ID: {result.aed_run_id}
                      </p>
                    )}
                  </div>

                  {finalReport ? (
                    <div className="app-card overflow-hidden">
                      <div className="border-b border-slate-800 px-4 py-3">
                        <h2 className="text-sm font-semibold text-slate-200">Relatório técnico AED</h2>
                        <p className="mt-0.5 text-xs text-slate-500">
                          Premissas, alternativas, normas e riscos — validação por engenheiro responsável
                        </p>
                      </div>
                      <div
                        className="prose prose-invert max-w-none px-4 py-4 text-sm leading-relaxed text-slate-300 prose-headings:text-slate-100 prose-li:text-slate-300"
                        dangerouslySetInnerHTML={{ __html: markdownToHtml(finalReport) }}
                      />
                    </div>
                  ) : (
                    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                      O pipeline não retornou relatório completo. Verifique se o Ollama está ativo e aguarde
                      todas as etapas ficarem verdes antes de interpretar o JSON abaixo.
                    </div>
                  )}

                  <div>
                    <button
                      type="button"
                      onClick={() => setShowRawJson((v) => !v)}
                      className="text-xs text-slate-500 hover:text-cyan-300"
                    >
                      {showRawJson ? "Ocultar JSON técnico" : "Ver JSON técnico (debug)"}
                    </button>
                    {showRawJson && (
                      <div className="mt-2">
                        <JsonViewer data={result} title="Resposta AED (completa)" />
                      </div>
                    )}
                  </div>
                </>
              );
            })()}
          </div>
        )}
      </div>
    </>
  );
}
