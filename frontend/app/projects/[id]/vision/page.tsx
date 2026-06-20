"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import LoadingSpinner from "@/components/LoadingSpinner";
import ProjectFilePreview from "@/components/ProjectFilePreview";
import ShellHeader from "@/components/ShellHeader";
import WorkspaceExpandButton, { WorkspaceCollapseStrip } from "@/components/WorkspaceExpandButton";
import { useActivity } from "@/context/ActivityContext";
import { api } from "@/services/api";
import type {
  ProjectDetail,
  ProjectFileItem,
  VisionAnalysisItem,
  VisionModeItem,
  VisionStatusResponse,
  VisionWorkspaceStatusResponse,
  VisionReportRequest,
  VisionAnalyzeProgress,
} from "@/types/api";
import { formatDate } from "@/lib/utils";

const VISUAL_EXT = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".bmp",
  ".tif",
  ".tiff",
  ".heic",
  ".heif",
  ".pdf",
]);

function isVisualFile(filename: string): boolean {
  const dot = filename.lastIndexOf(".");
  if (dot < 0) return false;
  return VISUAL_EXT.has(filename.slice(dot).toLowerCase());
}

function analysisPreview(item: VisionAnalysisItem): string {
  const tech = item.technical_report;
  if (tech?.resumo_executivo && typeof tech.resumo_executivo === "string") {
    return tech.resumo_executivo;
  }
  const data = item.analysis;
  if (!data) return item.error || (item.skipped ? "Formato não visual" : "Sem análise");
  const keys = [
    "resumo_tecnico",
    "legenda_relatorio",
    "legenda_laudo",
    "legenda_sugerida",
    "descricao_detalhada",
    "conclusao_parcial",
  ] as const;
  for (const key of keys) {
    const val = data[key];
    if (typeof val === "string" && val.trim()) return val;
  }
  return "Análise concluída.";
}

export default function ProjectVisionPage() {
  const params = useParams();
  const projectId = String(params.id);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [status, setStatus] = useState<VisionStatusResponse | null>(null);
  const [workspace, setWorkspace] = useState<VisionWorkspaceStatusResponse | null>(null);
  const [modes, setModes] = useState<VisionModeItem[]>([]);
  const [analyses, setAnalyses] = useState<VisionAnalysisItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState("obra");
  const [extraContext, setExtraContext] = useState("");
  const [obraInfo, setObraInfo] = useState("");
  const [solicitante, setSolicitante] = useState("");
  const [objeto, setObjeto] = useState("");
  const [discipline, setDiscipline] = useState("arquitetura");
  const [prazo, setPrazo] = useState("");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastSummary, setLastSummary] = useState<Record<string, unknown> | null>(null);
  const [visionProgress, setVisionProgress] = useState<VisionAnalyzeProgress | null>(null);
  const { pushActivity, updateActivity } = useActivity();

  const visualFiles = useMemo(
    () => (project?.files ?? []).filter((f) => isVisualFile(f.filename)),
    [project?.files]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [proj, st, ws, md, list] = await Promise.all([
        api.project(projectId),
        api.visionStatus(),
        api.visionWorkspaceStatus(),
        api.visionModes(),
        api.listVisionAnalyses(projectId),
      ]);
      setProject(proj);
      setStatus(st);
      setWorkspace(ws);
      setModes(md.modes);
      setAnalyses(list.items);
      const visual = proj.files.filter((f) => isVisualFile(f.filename));
      setSelectedIds(new Set(visual.map((f) => f.id)));
      if (proj.description) setObjeto(proj.description);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar análise visual");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleFile = (file: ProjectFileItem) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(file.id)) next.delete(file.id);
      else next.add(file.id);
      return next;
    });
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setError(null);
    setVisionProgress({
      phase: "prepare",
      current: 0,
      total: selectedIds.size || visualFiles.length,
      percent: 0,
      message: "Iniciando análise…",
    });
    const liveId = `vision-${Date.now()}`;
    pushActivity({
      id: liveId,
      source: "vision",
      message: `Análise visual (${mode}) iniciada`,
      status: "running",
      phase: "prepare",
      projectId,
    });
    try {
      const fileIds = selectedIds.size ? Array.from(selectedIds) : undefined;
      const result = await api.analyzeVisionWithProgress(
        projectId,
        { file_ids: fileIds, mode, extra_context: extraContext },
        (progress) => {
          setVisionProgress(progress);
          updateActivity(liveId, {
            message: progress.message,
            phase: progress.phase,
          });
        },
        (item) => {
          setAnalyses((prev) => {
            const next = prev.filter((a) => a.project_file_id !== item.project_file_id);
            return [...next, item];
          });
        }
      );
      setAnalyses(result.items);
      setLastSummary(result.summary);
      setVisionProgress({
        phase: "complete",
        current: result.total,
        total: result.total,
        percent: 100,
        message: "Análise concluída",
      });
      updateActivity(liveId, {
        status: "done",
        message: `Análise concluída: ${result.analyzed}/${result.total}`,
        phase: mode,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na análise visual");
      setVisionProgress(null);
      updateActivity(liveId, {
        status: "error",
        message: err instanceof Error ? err.message : "Falha na análise visual",
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleExport = async (reportType: VisionReportRequest["report_type"]) => {
    setExporting(reportType);
    setError(null);
    try {
      await api.exportVisionReport(projectId, {
        report_type: reportType,
        file_ids: selectedIds.size ? Array.from(selectedIds) : [],
        obra_info: obraInfo,
        solicitante,
        objeto,
        discipline,
        prazo,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar relatório");
    } finally {
      setExporting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <LoadingSpinner label="Carregando análise visual..." size="lg" />
      </div>
    );
  }

  const visionReady = status?.available ?? false;

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
              {" / Análise Visual"}
            </p>
            <h1 className="truncate text-lg font-semibold text-white">
              Vision Engine — Gemma3 + Qwen3
            </h1>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            disabled={analyzing || !visionReady || visualFiles.length === 0}
            onClick={handleAnalyze}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {analyzing ? "Analisando..." : "Analisar selecionadas"}
          </button>
        </div>
      </ShellHeader>

      {error && (
        <div className="mx-6 mt-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
          {error}
        </div>
      )}

      {(analyzing || visionProgress) && (
        <div className="mx-6 mt-4 rounded-xl bg-slate-900/80 px-4 py-3 ring-1 ring-slate-800">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-slate-300">
              {visionProgress?.message ?? "Processando…"}
            </span>
            <span className="font-mono text-emerald-400">
              {visionProgress?.percent ?? 0}%
              {visionProgress?.total
                ? ` · ${visionProgress.current}/${visionProgress.total}`
                : ""}
            </span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full bg-slate-800"
            role="progressbar"
            aria-valuenow={visionProgress?.percent ?? 0}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full bg-emerald-500 transition-all duration-500 ease-out"
              style={{ width: `${visionProgress?.percent ?? 0}%` }}
            />
          </div>
          {visionProgress?.phase && (
            <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
              Fase: {visionProgress.phase}
              {visionProgress.filename ? ` — ${visionProgress.filename}` : ""}
            </p>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800 lg:col-span-1">
            <h2 className="mb-4 font-medium text-white">Status da visão</h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between text-slate-400">
                <dt>Pipeline</dt>
                <dd className={workspace?.ready ? "text-emerald-400" : "text-amber-300"}>
                  {workspace?.ready ? "Pronto" : "Parcial"}
                </dd>
              </div>
              <div className="flex justify-between text-slate-400">
                <dt>Ollama</dt>
                <dd className={status?.ollama_reachable ? "text-emerald-400" : "text-red-300"}>
                  {status?.ollama_reachable ? "Online" : "Offline"}
                </dd>
              </div>
              <div className="flex justify-between text-slate-400">
                <dt>Visão (Gemma3)</dt>
                <dd className={visionReady ? "text-emerald-400" : "text-amber-300"}>
                  {visionReady
                    ? status?.vision_models_ready?.[0] ?? "gemma3:12b"
                    : "Indisponível"}
                </dd>
              </div>
              <div className="flex justify-between text-slate-400">
                <dt>Relatório (Qwen3)</dt>
                <dd className={workspace?.technical_model_ready ? "text-emerald-400" : "text-amber-300"}>
                  {workspace?.technical_model_ready ? workspace.technical_model : "Indisponível"}
                </dd>
              </div>
              <div className="flex justify-between text-slate-400">
                <dt>Arquivos visuais</dt>
                <dd className="text-white">{visualFiles.length}</dd>
              </div>
              <div className="flex justify-between text-slate-400">
                <dt>Análises salvas</dt>
                <dd className="text-white">{analyses.length}</dd>
              </div>
            </dl>
            {!visionReady && (
              <p className="mt-4 text-xs text-amber-300/90">
                Modelo multimodal necessário:{" "}
                <code className="rounded bg-slate-800 px-1">gemma3:12b</code> (já instalado no seu
                Ollama — verifique se o backend está rodando).
              </p>
            )}

            {workspace?.analyzers && (
              <div className="mt-6">
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                  Analisadores
                </h3>
                <ul className="space-y-1 text-xs">
                  {workspace.analyzers.map((a) => (
                    <li key={a.id} className="flex justify-between text-slate-400">
                      <span>{a.label}</span>
                      <span className={a.available ? "text-emerald-400" : "text-red-300"}>
                        {a.available ? "OK" : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {workspace?.pipeline && (
              <div className="mt-4 text-xs text-slate-500">
                {workspace.pipeline.join(" → ")}
              </div>
            )}

            <div className="mt-6 space-y-3">
              <label className="block text-sm text-slate-400">
                Modo de análise
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                >
                  {modes.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm text-slate-400">
                Contexto adicional
                <textarea
                  value={extraContext}
                  onChange={(e) => setExtraContext(e.target.value)}
                  rows={3}
                  placeholder="Ex.: frente de serviço, pavimento, referência normativa..."
                  className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                />
              </label>
            </div>
          </section>

          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800 lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-medium text-white">Arquivos para análise</h2>
              {visualFiles.length > 0 && (
                <button
                  type="button"
                  onClick={() =>
                    setSelectedIds(
                      selectedIds.size === visualFiles.length
                        ? new Set()
                        : new Set(visualFiles.map((f) => f.id))
                    )
                  }
                  className="text-xs text-cyan-400 hover:text-cyan-300"
                >
                  {selectedIds.size === visualFiles.length ? "Desmarcar todos" : "Selecionar todos"}
                </button>
              )}
            </div>
            {visualFiles.length === 0 ? (
              <p className="text-sm text-slate-500">
                Nenhuma foto ou PDF no projeto. Faça upload de imagens (PNG, JPG, WebP, HEIC) ou
                plantas PDF na página do projeto.
              </p>
            ) : (
              <ul className="mb-4 space-y-2">
                {visualFiles.map((file) => (
                  <li
                    key={file.id}
                    className="flex items-center gap-3 rounded-xl bg-slate-800/50 px-3 py-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(file.id)}
                      onChange={() => toggleFile(file)}
                      className="rounded border-slate-600 bg-slate-900 text-emerald-500"
                    />
                    <ProjectFilePreview
                      projectId={projectId}
                      fileId={file.id}
                      alt={file.filename}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-slate-200">{file.filename}</p>
                      <p className="text-xs text-slate-500">
                        {file.size_bytes ? `${Math.round(file.size_bytes / 1024)} KB` : "—"}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {lastSummary && (
              <div className="rounded-xl bg-slate-800/40 p-4 text-sm">
                <h3 className="mb-2 font-medium text-white">Resumo da última execução</h3>
                <p className="text-slate-300">
                  {String(lastSummary.analyzed ?? 0)} analisada(s) · {String(lastSummary.errors ?? 0)}{" "}
                  erro(s) · {String(lastSummary.skipped ?? 0)} ignorada(s)
                </p>
                {Array.isArray(lastSummary.nao_conformidades) &&
                  (lastSummary.nao_conformidades as string[]).length > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-slate-400">
                      {(lastSummary.nao_conformidades as string[]).slice(0, 5).map((nc) => (
                        <li key={nc}>{nc}</li>
                      ))}
                    </ul>
                  )}
              </div>
            )}
          </section>

          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800 lg:col-span-3">
            <h2 className="mb-4 font-medium text-white">Resultados ({analyses.length})</h2>
            {analyses.length === 0 ? (
              <p className="text-sm text-slate-500">
                Execute a análise para gerar laudos parciais, legendas e NCs por imagem.
              </p>
            ) : (
              <ul className="space-y-3">
                {analyses.map((item) => (
                  <li
                    key={item.project_file_id}
                    className="flex gap-4 rounded-xl bg-slate-800/50 px-4 py-3 text-sm ring-1 ring-slate-700/50"
                  >
                    <ProjectFilePreview
                      projectId={projectId}
                      fileId={item.project_file_id}
                      alt={item.filename}
                      className="h-24 w-32 shrink-0 rounded-lg object-cover ring-1 ring-slate-600"
                    />
                    <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <span className="font-medium text-slate-200">{item.filename}</span>
                      <span className="rounded bg-slate-700 px-2 py-0.5 text-xs uppercase text-slate-300">
                        {item.analysis_mode}
                      </span>
                      {item.analyzer && (
                        <span className="rounded bg-emerald-900/40 px-2 py-0.5 text-xs text-emerald-300">
                          {item.analyzer}
                        </span>
                      )}
                      {item.error && (
                        <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs text-red-300">
                          Erro
                        </span>
                      )}
                      {item.skipped && (
                        <span className="rounded bg-slate-600/40 px-2 py-0.5 text-xs text-slate-400">
                          Ignorado
                        </span>
                      )}
                    </div>
                    <p className="text-slate-300">{analysisPreview(item)}</p>
                    {item.analyzed_at && (
                      <p className="mt-1 text-xs text-slate-500">
                        {item.model_used ? `Gemma: ${item.model_used}` : ""}
                        {item.technical_model_used
                          ? ` · Qwen: ${item.technical_model_used}`
                          : ""}
                        {item.analyzed_at ? ` · ${formatDate(item.analyzed_at)}` : ""}
                      </p>
                    )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800 lg:col-span-3">
            <h2 className="mb-4 font-medium text-white">Exportar documentos</h2>
            <div className="grid gap-4 md:grid-cols-4">
              <label className="block text-sm text-slate-400">
                Disciplina (memorial)
                <input
                  value={discipline}
                  onChange={(e) => setDiscipline(e.target.value)}
                  placeholder="arquitetura, estrutura, pci..."
                  className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                />
              </label>
              <label className="block text-sm text-slate-400">
                Prazo correções
                <input
                  value={prazo}
                  onChange={(e) => setPrazo(e.target.value)}
                  placeholder="Ex.: 15 dias úteis"
                  className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                />
              </label>
              <label className="block text-sm text-slate-400 md:col-span-2">
                Dados da obra
                <input
                  value={obraInfo}
                  onChange={(e) => setObraInfo(e.target.value)}
                  placeholder="Endereço, contrato, etapa..."
                  className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                />
              </label>
              <label className="block text-sm text-slate-400">
                Solicitante (laudo)
                <input
                  value={solicitante}
                  onChange={(e) => setSolicitante(e.target.value)}
                  placeholder="Contratante / fiscal"
                  className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                />
              </label>
              <label className="block text-sm text-slate-400 md:col-span-3">
                Objeto (laudo)
                <input
                  value={objeto}
                  onChange={(e) => setObjeto(e.target.value)}
                  placeholder="Objeto da vistoria"
                  className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                />
              </label>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {(
                [
                  ["tecnico", "Relatório Técnico"],
                  ["relatorio_fotografico", "Relatório Fotográfico"],
                  ["laudo", "Laudo de Vistoria"],
                  ["correcoes", "Relatório de Correções"],
                  ["review", "Revisão Técnica"],
                  ["nc", "Relatório NCs"],
                  ["parecer", "Parecer Técnico"],
                  ["memorial", "Memorial Descritivo"],
                  ["tdr", "TDR"],
                ] as const
              ).map(([type, label]) => (
                <button
                  key={type}
                  type="button"
                  disabled={
                    exporting !== null ||
                    (type !== "review" &&
                      type !== "nc" &&
                      type !== "parecer" &&
                      type !== "memorial" &&
                      type !== "tdr" &&
                      analyses.length === 0)
                  }
                  onClick={() => handleExport(type)}
                  className="rounded-lg bg-slate-800 px-3 py-2 text-xs font-medium text-cyan-300 ring-1 ring-slate-700 hover:bg-slate-700 disabled:opacity-50"
                >
                  {exporting === type ? "Gerando..." : label}
                </button>
              ))}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
