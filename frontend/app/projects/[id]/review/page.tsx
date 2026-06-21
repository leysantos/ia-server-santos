"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import WorkspaceExpandButton, { WorkspaceCollapseStrip } from "@/components/WorkspaceExpandButton";
import { api } from "@/services/api";
import type { NCSummary, ReviewDashboard, ReviewDetail, ReviewSummary } from "@/types/api";
import { formatDate } from "@/lib/utils";

function ScoreBar({ label, value }: { label: string; value?: number }) {
  const v = value ?? 0;
  const color = v >= 80 ? "bg-emerald-500" : v >= 60 ? "bg-amber-500" : "bg-red-500";
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span>{v.toFixed(0)}/100</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(100, v)}%` }} />
      </div>
    </div>
  );
}

const STATUS_LABELS: Record<string, string> = {
  recebido: "Recebido",
  em_processamento: "Em Processamento",
  analisado: "Analisado",
  com_pendencias: "Com Pendências",
  aguardando_correcao: "Aguardando Correção",
  revisado: "Revisado",
  aprovado: "Aprovado",
};

export default function ProjectReviewPage() {
  const params = useParams();
  const projectId = String(params.id);

  const [dashboard, setDashboard] = useState<ReviewDashboard | null>(null);
  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  const [selectedReview, setSelectedReview] = useState<ReviewDetail | null>(null);
  const [ncs, setNcs] = useState<NCSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dash, revList] = await Promise.all([
        api.reviewDashboard(projectId),
        api.listReviews(projectId),
      ]);
      setDashboard(dash);
      setReviews(revList.items);
      if (dash.latest_review?.id) {
        const detail = await api.getReview(projectId, dash.latest_review.id);
        setSelectedReview(detail);
        const ncList = await api.listReviewNCs(projectId, dash.latest_review.id);
        setNcs(ncList.items);
      } else {
        setSelectedReview(null);
        setNcs([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar revisão");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStartReview = async () => {
    setRunning(true);
    setError(null);
    try {
      // Reutiliza análises visuais já salvas — não reexecuta Gemma/Qwen na GPU.
      const result = await api.startReview(projectId, { enable_vision: true });
      setSelectedReview(result);
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha ao iniciar revisão";
      if (msg.includes("409") || msg.toLowerCase().includes("análise visual")) {
        setError(
          `${msg} Conclua ou cancele a análise visual em /vision antes de iniciar a revisão.`
        );
      } else {
        setError(msg);
      }
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <LoadingSpinner label="Carregando revisão..." size="lg" />
      </div>
    );
  }

  const scores = selectedReview?.scores ?? dashboard?.scores ?? undefined;

  return (
    <>
      <WorkspaceCollapseStrip />
      <ShellHeader className="px-6" showModelsStatus>
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <WorkspaceExpandButton />
          <div className="min-w-0">
            <p className="text-xs text-slate-500">
              <Link href="/projects" className="hover:text-cyan-400">
                Projetos
              </Link>
              {" / "}
              <Link href={`/projects/${projectId}`} className="hover:text-cyan-400">
                Projeto
              </Link>
              {" / Revisão Técnica"}
            </p>
            <h1 className="truncate text-lg font-semibold text-white">Project Review Engine</h1>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            disabled={running}
            onClick={handleStartReview}
            className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
          >
            {running ? "Processando..." : "Iniciar Revisão"}
          </button>
        </div>
      </ShellHeader>

      {error && (
        <div className="mx-6 mt-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
          {error}
        </div>
      )}

      <p className="mx-6 mt-3 text-xs text-slate-500">
        Reutiliza análises visuais já salvas no projeto. Se houver análise visual em andamento,
        aguarde a conclusão ou cancele no{" "}
        <Link href="/console" className="text-cyan-400 hover:text-cyan-300">
          Console
        </Link>{" "}
        antes de iniciar.
      </p>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800 lg:col-span-1">
            <h2 className="mb-4 font-medium text-white">Indicadores</h2>
            <div className="space-y-3">
              <ScoreBar label="Conformidade Geral" value={scores?.conformidade_geral} />
              <ScoreBar label="Estrutural" value={scores?.conformidade_estrutural} />
              <ScoreBar label="PCI" value={scores?.conformidade_pci} />
              <ScoreBar label="Documental" value={scores?.conformidade_documental} />
              <ScoreBar label="Orçamentária" value={scores?.conformidade_orcamentaria} />
            </div>
            <dl className="mt-6 space-y-2 text-sm">
              <div className="flex justify-between text-slate-400">
                <dt>Revisões</dt>
                <dd className="text-white">{dashboard?.reviews_total ?? 0}</dd>
              </div>
              <div className="flex justify-between text-slate-400">
                <dt>NCs abertas</dt>
                <dd className="text-amber-300">{dashboard?.pending_ncs ?? 0}</dd>
              </div>
              <div className="flex justify-between text-slate-400">
                <dt>Total NCs</dt>
                <dd className="text-white">{dashboard?.ncs_total ?? 0}</dd>
              </div>
            </dl>
          </section>

          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800 lg:col-span-2">
            <h2 className="mb-4 font-medium text-white">Revisões</h2>
            {reviews.length === 0 ? (
              <p className="text-sm text-slate-500">
                Nenhuma revisão executada. Faça upload dos documentos no projeto e clique em
                Iniciar Revisão.
              </p>
            ) : (
              <ul className="mb-6 space-y-2">
                {reviews.map((rev) => (
                  <li
                    key={rev.id}
                    className="flex items-center justify-between rounded-xl bg-slate-800/50 px-3 py-2 text-sm"
                  >
                    <div>
                      <p className="font-medium text-slate-200">
                        v{rev.version} — {STATUS_LABELS[rev.status] ?? rev.status}
                      </p>
                      <p className="text-xs text-slate-500">
                        {rev.completed_at ? formatDate(rev.completed_at) : formatDate(rev.created_at ?? "")}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <a
                        href={api.exportReviewReport(projectId, rev.id, "review")}
                        className="text-xs text-cyan-400 hover:text-cyan-300"
                      >
                        Relatório
                      </a>
                      <a
                        href={api.exportReviewReport(projectId, rev.id, "nc")}
                        className="text-xs text-cyan-400 hover:text-cyan-300"
                      >
                        NCs
                      </a>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {selectedReview?.analysis_payload && (
              <div className="rounded-xl bg-slate-800/40 p-4">
                <h3 className="mb-2 text-sm font-medium text-white">Resumo da análise</h3>
                <p className="text-sm text-slate-300">
                  {String(
                    (selectedReview.analysis_payload as Record<string, unknown>).resumo ||
                      "Análise concluída."
                  )}
                </p>
              </div>
            )}
          </section>

          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800 lg:col-span-3">
            <h2 className="mb-4 font-medium text-white">
              Não Conformidades ({ncs.length})
            </h2>
            {ncs.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhuma NC registrada na última revisão.</p>
            ) : (
              <ul className="space-y-2">
                {ncs.map((nc) => (
                  <li
                    key={nc.id}
                    className="rounded-xl bg-slate-800/50 px-4 py-3 text-sm ring-1 ring-slate-700/50"
                  >
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <span className="font-mono text-cyan-400">{nc.codigo}</span>
                      <span className="rounded bg-slate-700 px-2 py-0.5 text-xs uppercase text-slate-300">
                        {nc.categoria}
                      </span>
                      <span
                        className={`rounded px-2 py-0.5 text-xs uppercase ${
                          nc.criticidade === "critica" || nc.criticidade === "alta"
                            ? "bg-red-500/20 text-red-300"
                            : "bg-amber-500/20 text-amber-300"
                        }`}
                      >
                        {nc.criticidade}
                      </span>
                    </div>
                    <p className="text-slate-200">{nc.descricao}</p>
                    {nc.recomendacao && (
                      <p className="mt-1 text-xs text-slate-500">Recomendação: {nc.recomendacao}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
