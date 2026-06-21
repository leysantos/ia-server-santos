"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import WorkspaceExpandButton, { WorkspaceCollapseStrip } from "@/components/WorkspaceExpandButton";
import { api } from "@/services/api";
import type { WorkflowProjectState } from "@/types/api";
import { formatDate } from "@/lib/utils";

export default function ProjectWorkflowPage() {
  const params = useParams();
  const projectId = String(params.id);

  const [state, setState] = useState<WorkflowProjectState | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setState(await api.projectWorkflow(projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar workflow");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!activeJobId) return;
    const timer = setInterval(async () => {
      try {
        const job = await api.workflowJob(activeJobId);
        if (job.status === "completed") {
          setActiveJobId(null);
          setNotice("Pipeline concluído em background.");
          await load();
        } else if (job.status === "failed") {
          setActiveJobId(null);
          setError(job.error || "Pipeline falhou");
        }
      } catch {
        /* polling silencioso */
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [activeJobId, load]);

  const handleProcess = async (force = false) => {
    setProcessing(true);
    setNotice(null);
    setError(null);
    try {
      const result = await api.processProjectWorkflow(projectId, { force });
      if (result.job_id && result.mode !== "sync") {
        setActiveJobId(result.job_id);
        setNotice(`Pipeline enfileirado (${result.mode}) — job ${result.job_id.slice(0, 8)}…`);
      } else if (result.processed != null) {
        const skipped = result.skipped ? ` · ${result.skipped} ignorado(s)` : "";
        setNotice(
          `Pipeline concluído — ${result.pranchas ?? 0} prancha(s), ${result.documentos ?? 0} documento(s) indexado(s)${skipped}.`,
        );
        await load();
      } else {
        setNotice("Pipeline iniciado.");
        await load();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao processar workflow");
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <LoadingSpinner label="Carregando workflow..." size="lg" />
      </div>
    );
  }

  if (!state) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-red-300">
        {error || "Workflow não encontrado"}
      </div>
    );
  }

  const { project, summary, inventory } = state;

  return (
    <>
      <WorkspaceCollapseStrip />
      <ShellHeader
        className="px-6"
        showModelsStatus
        trailing={
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              disabled={processing}
              onClick={() => handleProcess(false)}
              className="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
            >
              {processing ? "Processando..." : "Executar pipeline"}
            </button>
            <Link
              href={`/projects/${projectId}/workflow/wizard`}
              className="rounded-lg bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-500"
            >
              Wizard de entrega
            </Link>
            <button
              type="button"
              disabled={processing}
              onClick={() => handleProcess(true)}
              className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-amber-300 ring-1 ring-amber-600/40 hover:bg-slate-700 disabled:opacity-50"
              title="Reprocessa todos os arquivos, mesmo os já indexados"
            >
              Reprocessar tudo
            </button>
            <Link
              href={`/projects/${projectId}`}
              className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-300 ring-1 ring-slate-700 hover:bg-slate-700"
            >
              Voltar ao projeto
            </Link>
          </div>
        }
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <WorkspaceExpandButton />
          <div className="min-w-0">
            <p className="text-xs text-slate-500">
              <Link href="/projects" className="hover:text-cyan-400">
                Projetos
              </Link>
              {" / "}
              <Link href={`/projects/${projectId}`} className="hover:text-cyan-400">
                {project.name}
              </Link>
              {" / Workflow"}
            </p>
            <h1 className="truncate text-lg font-semibold text-white">Workflow Projetos</h1>
            <p className="mt-0.5 text-sm text-slate-400">
              Revisão {project.versao_atual} · {project.workflow_initialized ? "Estrutura criada" : "Não inicializado"}
            </p>
          </div>
        </div>
      </ShellHeader>

      {error && (
        <div className="mx-6 mt-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
          {error}
        </div>
      )}
      {notice && (
        <div className="mx-6 mt-4 rounded-xl bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300 ring-1 ring-emerald-500/30">
          {notice}
        </div>
      )}

      <div className="flex-1 overflow-auto p-6">
        {summary && (
          <div className="mx-auto mb-6 max-w-6xl rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
            <h2 className="mb-2 font-medium text-white">Resumo do projeto</h2>
            <p className="text-sm text-slate-400">
              {summary.arquivos_suportados} arquivo(s) elegíveis ·{" "}
              <span className="text-cyan-300">{summary.pranchas} prancha(s)</span> ·{" "}
              <span className="text-emerald-300">{summary.documentos} documento(s)</span> indexados ·{" "}
              {summary.pranchas_geradas} prancha(s) gerada(s) · {summary.entregas} entrega(s)
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Pranchas (ARQ/PPCI com revisão) passam pelo pipeline completo. Documentos (memorial, parecer,
              memória de cálculo, termo) são apenas catalogados — não geram revisão nem entrega.
            </p>
          </div>
        )}

        <div className="mx-auto grid max-w-6xl gap-4 md:grid-cols-3">
          <StatCard label="Pastas" value={state.folders.length} />
          <StatCard label="Arquivos indexados" value={state.drawings.length} />
          <StatCard label="Pranchas geradas" value={state.sheets.length} />
          <StatCard label="Revisões" value={state.revisions.length} />
          <StatCard label="Commits" value={state.versions.length} />
          <StatCard label="Eventos" value={state.events.length} />
          <StatCard label="Entregas" value={state.deliveries?.length ?? 0} />
        </div>

        <div className="mx-auto mt-6 grid max-w-6xl gap-6 lg:grid-cols-2">
          <Panel title="Inventário de arquivos">
            {!inventory?.length ? (
              <p className="text-sm text-slate-500">Nenhum PDF/CAD/BIM no projeto.</p>
            ) : (
              <ul className="max-h-96 space-y-2 overflow-auto text-sm">
                {inventory.map((item) => (
                  <li key={item.file_id} className="rounded-lg bg-slate-800/40 px-3 py-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-slate-200" title={item.filename}>
                        {item.filename}
                      </span>
                      <div className="flex shrink-0 items-center gap-2">
                        <TipoBadge tipo={item.tipo_arquivo} />
                        {item.processed ? (
                          <span className="text-xs text-emerald-400">ok</span>
                        ) : (
                          <span className="text-xs text-slate-500">pendente</span>
                        )}
                      </div>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {item.subtipo} · pipeline {item.pipeline === "full" ? "completo" : "indexação"}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Jobs assíncronos">
            {!state.jobs?.length ? (
              <p className="text-sm text-slate-500">Nenhum job — upload CAD/BIM dispara processamento em background.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {state.jobs.map((j) => (
                  <li key={j.id} className="rounded-lg bg-slate-800/40 px-3 py-2">
                    <div className="flex justify-between gap-2">
                      <span className="text-slate-200">{j.job_type}</span>
                      <span className="text-xs uppercase text-cyan-300">{j.status}</span>
                    </div>
                    <p className="text-xs text-slate-500">{formatDate(j.created_at)}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Publicações (PDF / ZIP)">
            {!state.deliveries?.length ? (
              <p className="text-sm text-slate-500">Execute o pipeline para gerar PDF e pacote de entrega.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {state.deliveries.map((d) => (
                  <li key={d.id} className="rounded-lg bg-slate-800/40 px-3 py-2">
                    <div className="flex justify-between text-slate-200">
                      <span>{d.status}</span>
                      <span className="text-xs text-slate-500">{formatDate(d.created_at)}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(d.pdf_download_url || d.pdf_key) && (
                        <a
                          href={api.workflowArtifactHref(d.pdf_download_url || d.pdf_key || "")}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-cyan-400 hover:text-cyan-300"
                        >
                          PDF
                        </a>
                      )}
                      {(d.zip_download_url || d.zip_key || d.package_path) && (
                        <a
                          href={api.workflowArtifactHref(
                            d.zip_download_url || d.zip_key || d.package_path || "",
                          )}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-emerald-400 hover:text-emerald-300"
                        >
                          ZIP
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Estrutura de pastas">
            {state.folders.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhuma pasta — crie o projeto ou execute o pipeline.</p>
            ) : (
              <ul className="space-y-1 text-sm text-slate-300">
                {state.folders.map((f) => (
                  <li key={f.id} className="flex justify-between rounded-lg bg-slate-800/40 px-3 py-2">
                    <span>{f.nome}</span>
                    <span className="text-xs text-slate-500">{f.disciplina || f.path}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Revisões">
            {state.revisions.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhuma revisão registrada.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {state.revisions.map((r) => (
                  <li key={r.id} className="rounded-lg bg-slate-800/40 px-3 py-2">
                    <div className="flex justify-between text-slate-200">
                      <span className="font-medium">{r.codigo}</span>
                      <span className="text-xs text-slate-500">{formatDate(r.created_at)}</span>
                    </div>
                    <p className="text-xs text-slate-400">{r.descricao || "—"}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Pranchas geradas">
            {state.sheets.length === 0 ? (
              <p className="text-sm text-slate-500">Envie DWG/DXF/IFC e execute o pipeline.</p>
            ) : (
              <ul className="space-y-2 text-sm text-slate-300">
                {state.sheets.map((s) => (
                  <li key={s.id} className="rounded-lg bg-slate-800/40 px-3 py-2">
                    Prancha {s.numero_prancha} · {s.escala} · {s.status}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Eventos recentes">
            {state.events.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhum evento ainda.</p>
            ) : (
              <ul className="max-h-80 space-y-2 overflow-auto text-sm">
                {state.events.map((e) => (
                  <li key={e.id} className="rounded-lg bg-slate-800/40 px-3 py-2">
                    <div className="flex justify-between gap-2">
                      <span className="font-mono text-xs text-cyan-300">{e.event_type}</span>
                      <span className="shrink-0 text-xs text-slate-500">{formatDate(e.created_at)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
      <h2 className="mb-3 font-medium text-white">{title}</h2>
      {children}
    </section>
  );
}

function TipoBadge({ tipo }: { tipo: string }) {
  const styles =
    tipo === "prancha"
      ? "bg-cyan-500/15 text-cyan-300 ring-cyan-500/30"
      : tipo === "documento"
        ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
        : "bg-slate-700/50 text-slate-300 ring-slate-600/30";
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ring-1 ${styles}`}>
      {tipo}
    </span>
  );
}
