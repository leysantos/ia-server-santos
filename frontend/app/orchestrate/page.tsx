"use client";

import { useState } from "react";
import ChatBox from "@/components/ChatBox";
import JsonViewer from "@/components/JsonViewer";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import { api } from "@/services/api";
import type { OrchestrateResponse } from "@/types/api";

export default function OrchestratePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OrchestrateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSend = async (
    text: string,
    options: { useRag: boolean; persist: boolean }
  ) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.orchestrate({
        text,
        use_rag: options.useRag,
        persist: options.persist,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro na orquestração");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <ShellHeader className="px-6">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Orquestrador Multidisciplinar</h1>
          <p className="text-sm text-slate-500">
            Decomposição automática → múltiplos agentes → relatório unificado
          </p>
        </div>
      </ShellHeader>

      <div className="flex-1 overflow-y-auto px-6 py-6">
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
