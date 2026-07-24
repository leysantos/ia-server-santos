"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ShellHeader from "@/components/ShellHeader";
import InspectionPartyList from "@/components/InspectionPartyList";
import { useActionDialog } from "@/hooks/useActionDialog";
import { api } from "@/services/api";
import { downloadApiFile } from "@/services/api/http";
import type {
  InspectionReport,
  InspectionReportGenerateProgress,
  InspectionReportParty,
  InspectionReportSolicitante,
  InspectionReportTemplate,
} from "@/types/api";

function partiesFromContent(content: Record<string, unknown> | null | undefined, key: string): InspectionReportParty[] {
  const raw = content?.[key];
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item, idx) => {
      if (!item || typeof item !== "object") return null;
      const o = item as Record<string, unknown>;
      const nome = String(o.nome || "").trim();
      if (!nome) return null;
      return {
        id: String(o.id || `p_${idx}_${nome}`),
        nome,
        profissao: String(o.profissao || ""),
        crea: String(o.crea || ""),
        art: String(o.art || ""),
        email: String(o.email || ""),
        telefone: String(o.telefone || ""),
      } satisfies InspectionReportParty;
    })
    .filter((p): p is InspectionReportParty => p !== null);
}

function solicitanteFromContent(
  content: Record<string, unknown> | null | undefined
): InspectionReportSolicitante {
  const raw = content?.solicitante;
  if (!raw || typeof raw !== "object") {
    return { empresa: "", cnpj: "", endereco: "", contato: "" };
  }
  const o = raw as Record<string, unknown>;
  return {
    empresa: String(o.empresa || ""),
    cnpj: String(o.cnpj || ""),
    endereco: String(o.endereco || ""),
    contato: String(o.contato || ""),
  };
}

const GENERATE_STAGES = [
  { id: "prepare", label: "Preparar laudo e validar dados", cap: 16 },
  { id: "attachments", label: "Ler documentos e fotografias", cap: 34 },
  { id: "knowledge", label: "Consultar base de conhecimento (RAG)", cap: 52 },
  { id: "gemini", label: "Gerar conteúdo com Gemini", cap: 82 },
  { id: "structure", label: "Estruturar capítulos e fotos", cap: 90 },
  { id: "persist", label: "Salvar laudo gerado", cap: 97 },
  { id: "done", label: "Concluído", cap: 100 },
] as const;

const STAGE_CAP: Record<string, number> = Object.fromEntries(
  GENERATE_STAGES.map((s) => [s.id, s.cap])
);

function normalizeGeneratePhase(phase: string): string {
  if (phase === "start") return "prepare";
  if (phase === "error") return "persist";
  return phase;
}

function stageIndex(phase: string): number {
  const id = normalizeGeneratePhase(phase);
  const idx = GENERATE_STAGES.findIndex((s) => s.id === id);
  return idx >= 0 ? idx : 0;
}

function CircularProgress({
  percent,
  error,
  spinning,
}: {
  percent: number;
  error?: boolean;
  spinning?: boolean;
}) {
  const size = 128;
  const stroke = 9;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, percent));
  const offset = c - (pct / 100) * c;
  const strokeColor = error ? "#f43f5e" : pct >= 100 ? "#34d399" : "#22d3ee";

  return (
    <div className="relative mx-auto h-32 w-32" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <svg width={size} height={size} className="block -rotate-90" viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#1e293b"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={strokeColor}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.35s ease-out" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={`text-2xl font-semibold tabular-nums ${
            error ? "text-rose-300" : "text-cyan-200"
          }`}
        >
          {Math.round(pct)}%
        </span>
        {spinning && !error && pct < 100 && (
          <span className="mt-0.5 h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
        )}
      </div>
    </div>
  );
}

export default function InspectionReportsPage() {
  const { confirm, ActionDialogHost } = useActionDialog();
  const [templates, setTemplates] = useState<InspectionReportTemplate[]>([]);
  const [reports, setReports] = useState<InspectionReport[]>([]);
  const [active, setActive] = useState<InspectionReport | null>(null);
  const [status, setStatus] = useState<{ gemini_available: boolean; gemini_model: string } | null>(
    null
  );
  const [title, setTitle] = useState("Laudo de vistoria");
  const [templateId, setTemplateId] = useState("");
  const [knowledgeMode, setKnowledgeMode] = useState<"attachments" | "attachments_and_kb">(
    "attachments_and_kb"
  );
  const [userPrompt, setUserPrompt] = useState("");
  const [responsaveisTecnicos, setResponsaveisTecnicos] = useState<InspectionReportParty[]>([]);
  const [responsaveisImagens, setResponsaveisImagens] = useState<InspectionReportParty[]>([]);
  const [solicitante, setSolicitante] = useState<InspectionReportSolicitante>({
    empresa: "",
    cnpj: "",
    endereco: "",
    contato: "",
  });
  const [georefPreviewUrl, setGeorefPreviewUrl] = useState<string | null>(null);
  const [georefPreviewLoading, setGeorefPreviewLoading] = useState(false);
  const [exporting, setExporting] = useState<"docx" | "pdf" | null>(null);
  const [exportPct, setExportPct] = useState(0);
  const [exportError, setExportError] = useState(false);
  const exportTargetRef = useRef(0);
  const [correction, setCorrection] = useState("");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genProgress, setGenProgress] = useState<InspectionReportGenerateProgress | null>(null);
  const [displayPct, setDisplayPct] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [newTemplateName, setNewTemplateName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<Array<{ id: string; name: string }>>([]);
  const [checklist, setChecklist] = useState<{
    ok: boolean;
    blocking: boolean;
    issues: Array<{ code: string; message: string }>;
    warnings: Array<{ code: string; message: string }>;
    ready_for_official_export: boolean;
  } | null>(null);
  const [editChapters, setEditChapters] = useState<
    Array<{ id?: string; title?: string; paragraphs?: string[] }>
  >([]);
  const [editPhotos, setEditPhotos] = useState<
    Array<{ photo_number?: number; title?: string; legend?: string; description?: string }>
  >([]);
  const genAbortRef = useRef<AbortController | null>(null);
  const targetPctRef = useRef(0);
  const phaseRef = useRef("prepare");
  const generatingRef = useRef(false);

  const refresh = useCallback(async () => {
    const [tpl, list, st, proj] = await Promise.all([
      api.inspectionReportTemplates(),
      api.listInspectionReports(),
      api.inspectionReportStatus(),
      api.projects(100).catch(() => ({ items: [] as Array<{ id: string; name: string }> })),
    ]);
    setTemplates(tpl.items);
    setReports(list.items);
    setStatus(st);
    setProjects((proj.items || []).map((p) => ({ id: p.id, name: p.name || p.id })));
    if (!templateId && tpl.items[0]) setTemplateId(tpl.items[0].id);
  }, [templateId]);

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [refresh]);

  // Anima o círculo gradualmente em direção ao % do servidor + creep na etapa atual
  useEffect(() => {
    if (genProgress) {
      targetPctRef.current = Math.max(targetPctRef.current, genProgress.percent ?? 0);
      phaseRef.current = normalizeGeneratePhase(genProgress.phase || "prepare");
    }
  }, [genProgress]);

  useEffect(() => {
    generatingRef.current = generating;
  }, [generating]);

  useEffect(() => {
    if (!genProgress) {
      setDisplayPct(0);
      targetPctRef.current = 0;
      return;
    }
    const id = window.setInterval(() => {
      setDisplayPct((prev) => {
        const target = targetPctRef.current;
        if (prev < target) {
          const step = Math.max(0.4, (target - prev) * 0.18);
          return Math.min(target, prev + step);
        }
        if (generatingRef.current && genProgress.phase !== "done" && genProgress.phase !== "error") {
          const cap = STAGE_CAP[phaseRef.current] ?? 95;
          if (prev < cap - 0.3) {
            return Math.min(cap, prev + 0.12);
          }
        }
        return prev;
      });
    }, 80);
    return () => window.clearInterval(id);
  }, [genProgress, generating]);

  const selectedTemplate = useMemo(
    () => templates.find((t) => t.id === templateId) || null,
    [templates, templateId]
  );

  const createDraft = async () => {
    setLoading(true);
    setError(null);
    try {
      const report = await api.createInspectionReport({
        title,
        template_id: templateId || null,
        user_prompt: userPrompt,
        knowledge_mode: knowledgeMode,
        project_id: projectId || null,
      });
      setActive(report);
      setProjectId(report.project_id || "");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const openReport = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const report = await api.getInspectionReport(id);
      setActive(report);
      setTitle(report.title);
      setTemplateId(report.template_id || "");
      setProjectId(report.project_id || "");
      setUserPrompt(report.user_prompt || "");
      setKnowledgeMode(
        report.knowledge_mode === "attachments" ? "attachments" : "attachments_and_kb"
      );
      setResponsaveisTecnicos(
        partiesFromContent(report.content as Record<string, unknown> | null, "responsaveis_tecnicos")
      );
      setResponsaveisImagens(
        partiesFromContent(report.content as Record<string, unknown> | null, "responsaveis_imagens")
      );
      setSolicitante(solicitanteFromContent(report.content as Record<string, unknown> | null));
      const content = report.content as Record<string, unknown> | null;
      setEditChapters(
        Array.isArray(content?.chapters)
          ? (content!.chapters as Array<{ id?: string; title?: string; paragraphs?: string[] }>)
          : []
      );
      setEditPhotos(
        Array.isArray(content?.photographic_report)
          ? (content!.photographic_report as Array<{
              photo_number?: number;
              title?: string;
              legend?: string;
              description?: string;
            }>)
          : []
      );
      try {
        setChecklist(await api.inspectionReportExportChecklist(id));
      } catch {
        setChecklist(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const saveMeta = async () => {
    if (!active) return;
    setLoading(true);
    setError(null);
    try {
      const report = await api.updateInspectionReport(active.id, {
        title,
        template_id: templateId || null,
        user_prompt: userPrompt,
        knowledge_mode: knowledgeMode,
        project_id: projectId || null,
        responsaveis_tecnicos: responsaveisTecnicos,
        responsaveis_imagens: responsaveisImagens,
        solicitante,
      });
      setActive(report);
      setProjectId(report.project_id || "");
      setResponsaveisTecnicos(
        partiesFromContent(report.content as Record<string, unknown> | null, "responsaveis_tecnicos")
      );
      setResponsaveisImagens(
        partiesFromContent(report.content as Record<string, unknown> | null, "responsaveis_imagens")
      );
      setSolicitante(solicitanteFromContent(report.content as Record<string, unknown> | null));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const persistSolicitante = async (next: InspectionReportSolicitante) => {
    if (!active) return;
    setSolicitante(next);
    try {
      const report = await api.updateInspectionReport(active.id, { solicitante: next });
      setActive(report);
      setSolicitante(solicitanteFromContent(report.content as Record<string, unknown> | null));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const persistParties = async (
    nextTecnicos: InspectionReportParty[],
    nextImagens: InspectionReportParty[]
  ) => {
    if (!active) return;
    setResponsaveisTecnicos(nextTecnicos);
    setResponsaveisImagens(nextImagens);
    try {
      const report = await api.updateInspectionReport(active.id, {
        responsaveis_tecnicos: nextTecnicos,
        responsaveis_imagens: nextImagens,
      });
      setActive(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onUpload = async (files: FileList | null, kind?: string) => {
    if (!active || !files?.length) return;
    setLoading(true);
    setError(null);
    try {
      // Preview local imediato para imagem georref. (antes do round-trip)
      if (kind === "georef" && files[0]?.type.startsWith("image/")) {
        const localUrl = URL.createObjectURL(files[0]);
        setGeorefPreviewUrl((prev) => {
          if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
          return localUrl;
        });
        setGeorefPreviewLoading(false);
      }
      try {
        await api.updateInspectionReport(active.id, {
          title,
          template_id: templateId || null,
          user_prompt: userPrompt,
          knowledge_mode: knowledgeMode,
          responsaveis_tecnicos: responsaveisTecnicos,
          responsaveis_imagens: responsaveisImagens,
          solicitante,
        });
      } catch {
        // Upload não depende do save meta — continua mesmo se o patch falhar.
      }
      for (const file of Array.from(files)) {
        await api.uploadInspectionReportAsset(active.id, file, { kind });
      }
      await openReport(active.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const removeReport = async (id: string) => {
    const report = reports.find((r) => r.id === id) || (active?.id === id ? active : null);
    const title = report?.title?.trim() || "este laudo";
    const ok = await confirm({
      title: "Excluir laudo?",
      message:
        `Confirma a exclusão de “${title}”?\n\n` +
        "Todos os anexos (PDFs e fotos), o conteúdo gerado e o histórico de correções serão removidos permanentemente. Esta ação não pode ser desfeita.",
      confirmLabel: "Excluir laudo",
      cancelLabel: "Cancelar",
      destructive: true,
    });
    if (!ok) return;

    setLoading(true);
    setError(null);
    try {
      await api.deleteInspectionReport(id);
      if (active?.id === id) setActive(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const generate = async () => {
    if (!active || generating) return;
    setGenerating(true);
    generatingRef.current = true;
    setError(null);
    const abort = new AbortController();
    genAbortRef.current = abort;
    targetPctRef.current = 2;
    phaseRef.current = "prepare";
    setDisplayPct(2);
    setGenProgress({
      phase: "prepare",
      percent: 2,
      message: "Preparando geração do laudo…",
      report_id: active.id,
    });
    try {
      setGenProgress({
        phase: "prepare",
        percent: 5,
        message: "Salvando título, template e instruções…",
        report_id: active.id,
      });
      targetPctRef.current = 5;
      await api.updateInspectionReport(active.id, {
        title,
        template_id: templateId || null,
        user_prompt: userPrompt,
        knowledge_mode: knowledgeMode,
        project_id: projectId || null,
        responsaveis_tecnicos: responsaveisTecnicos,
        responsaveis_imagens: responsaveisImagens,
        solicitante,
      });
      setGenProgress({
        phase: "prepare",
        percent: 8,
        message: "Conectando ao gerador (SSE)…",
        report_id: active.id,
      });
      targetPctRef.current = 8;

      const report = await api.generateInspectionReportWithProgress(
        active.id,
        (p) => {
          const phase = normalizeGeneratePhase(p.phase || "prepare");
          phaseRef.current = phase;
          setGenProgress((prev) => {
            const nextPercent = Math.max(prev?.percent ?? 0, p.percent ?? 0);
            targetPctRef.current = Math.max(targetPctRef.current, nextPercent);
            return { ...p, phase: p.phase || phase, percent: nextPercent };
          });
        },
        abort.signal
      );
      setActive(report);
      targetPctRef.current = 100;
      phaseRef.current = "done";
      setGenProgress({
        phase: "done",
        percent: 100,
        message: "Laudo gerado com sucesso.",
        report_id: report.id,
      });
      await openReport(report.id);
      await refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (abort.signal.aborted || /abort|cancel/i.test(message)) {
        setGenProgress({
          phase: "error",
          percent: 100,
          message: "Geração cancelada.",
          report_id: active.id,
        });
      } else {
        setError(message);
        setGenProgress((prev) => ({
          phase: "error",
          percent: Math.max(prev?.percent ?? displayPct, 100),
          message: `Falha: ${message}`,
          report_id: active.id,
        }));
      }
    } finally {
      genAbortRef.current = null;
      setGenerating(false);
      generatingRef.current = false;
      window.setTimeout(() => {
        setGenProgress((prev) => (prev?.phase === "done" || prev?.phase === "error" ? null : prev));
      }, 1800);
    }
  };

  const cancelGenerate = async () => {
    if (!active) return;
    genAbortRef.current?.abort();
    try {
      await api.cancelInspectionReportGeneration(active.id);
    } catch {
      // ignore
    }
  };

  const applyCorrection = async () => {
    if (!active || !correction.trim() || generating) return;
    setGenerating(true);
    generatingRef.current = true;
    setError(null);
    const abort = new AbortController();
    genAbortRef.current = abort;
    targetPctRef.current = 2;
    phaseRef.current = "prepare";
    setDisplayPct(2);
    setGenProgress({
      phase: "prepare",
      percent: 2,
      message: "Preparando correção…",
      report_id: active.id,
    });
    try {
      const prompt = correction.trim();
      const report = await api.correctInspectionReportWithProgress(
        active.id,
        prompt,
        (p) => {
          const phase = normalizeGeneratePhase(p.phase || "prepare");
          phaseRef.current = phase;
          setGenProgress((prev) => {
            const nextPercent = Math.max(prev?.percent ?? 0, p.percent ?? 0);
            targetPctRef.current = Math.max(targetPctRef.current, nextPercent);
            return { ...p, phase: p.phase || phase, percent: nextPercent };
          });
        },
        abort.signal
      );
      setActive(report);
      setCorrection("");
      targetPctRef.current = 100;
      setGenProgress({
        phase: "done",
        percent: 100,
        message: "Correção concluída.",
        report_id: report.id,
      });
      await openReport(report.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setGenProgress((prev) => ({
        phase: "error",
        percent: Math.max(prev?.percent ?? displayPct, 100),
        message: `Falha: ${err instanceof Error ? err.message : String(err)}`,
        report_id: active.id,
      }));
    } finally {
      genAbortRef.current = null;
      setGenerating(false);
      generatingRef.current = false;
      window.setTimeout(() => {
        setGenProgress((prev) => (prev?.phase === "done" || prev?.phase === "error" ? null : prev));
      }, 1800);
    }
  };

  const saveHumanEdits = async () => {
    if (!active) return;
    setLoading(true);
    setError(null);
    try {
      const report = await api.updateInspectionReport(active.id, {
        chapters: editChapters,
        photographic_report: editPhotos,
      });
      setActive(report);
      setChecklist(await api.inspectionReportExportChecklist(active.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const download = async (fmt: "docx" | "pdf", strict = false) => {
    if (!active || exporting) return;
    setError(null);
    setExportError(false);
    setExporting(fmt);
    setExportPct(4);
    exportTargetRef.current = 12;

    const tick = window.setInterval(() => {
      setExportPct((prev) => {
        const target = exportTargetRef.current;
        if (prev >= target) return prev;
        return Math.min(target, prev + Math.max(0.6, (target - prev) * 0.12));
      });
    }, 120);

    try {
      if (strict) {
        const cl = await api.inspectionReportExportChecklist(active.id);
        setChecklist(cl);
        if (cl.blocking) {
          throw new Error(
            `Checklist oficial incompleto: ${cl.issues.map((i) => i.message).join("; ")}`
          );
        }
      }
      exportTargetRef.current = 55;
      const path =
        fmt === "docx"
          ? `/inspection-reports/${active.id}/export/docx${strict ? "?strict=true" : ""}`
          : `/inspection-reports/${active.id}/export/pdf${strict ? "?strict=true" : ""}`;
      const safeTitle = (active.title || "vistoria").slice(0, 40).replace(/[^\w\-]+/g, "_");
      await downloadApiFile(path, `laudo_${safeTitle}.${fmt}`);
      exportTargetRef.current = 100;
      setExportPct(100);
      await new Promise((r) => setTimeout(r, 450));
      setExporting(null);
      setExportPct(0);
    } catch (err) {
      setExportError(true);
      exportTargetRef.current = 100;
      setExportPct(100);
      setError(err instanceof Error ? err.message : String(err));
      await new Promise((r) => setTimeout(r, 1200));
      setExporting(null);
      setExportPct(0);
      setExportError(false);
    } finally {
      window.clearInterval(tick);
    }
  };

  const createTemplate = async () => {
    if (!newTemplateName.trim()) return;
    setLoading(true);
    try {
      await api.createInspectionReportTemplate({ name: newTemplateName.trim() });
      setNewTemplateName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const photos = (active?.assets || []).filter((a) => a.kind === "image");
  const georef = (active?.assets || []).find((a) => a.kind === "georef") || null;
  const docs = (active?.assets || []).filter((a) => a.kind !== "image" && a.kind !== "georef");

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    if (!active?.id || !georef?.id) {
      setGeorefPreviewUrl((prev) => {
        if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
        return null;
      });
      setGeorefPreviewLoading(false);
      return;
    }

    setGeorefPreviewLoading(true);
    api
      .fetchInspectionReportAssetFile(active.id, georef.id)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setGeorefPreviewUrl((prev) => {
          if (prev?.startsWith("blob:") && prev !== objectUrl) URL.revokeObjectURL(prev);
          return objectUrl;
        });
      })
      .catch(() => {
        // Mantém preview local (se houver) em caso de falha da API
        if (!cancelled) setGeorefPreviewLoading(false);
      })
      .finally(() => {
        if (!cancelled) setGeorefPreviewLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [active?.id, georef?.id]);

  const genPct = Math.min(100, Math.max(0, displayPct));
  const currentStageIdx = stageIndex(genProgress?.phase || "prepare");

  return (
    <>
      {exporting && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="laudo-export-title"
        >
          <div className="w-full max-w-sm rounded-2xl bg-slate-900 p-6 shadow-2xl ring-1 ring-cyan-500/30">
            <div className="mb-5 text-center">
              <h2 id="laudo-export-title" className="text-base font-semibold text-white">
                {exportError
                  ? "Falha na exportação"
                  : exportPct >= 100
                    ? "Download iniciado"
                    : exporting === "pdf"
                      ? "Exportando PDF"
                      : "Exportando Word"}
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                {exportError
                  ? "Não foi possível gerar o arquivo. Veja o erro na tela."
                  : exportPct >= 100
                    ? "O arquivo deve aparecer na pasta de downloads."
                    : "Montando o laudo com cabeçalho, fotos e marca d'água…"}
              </p>
            </div>
            <CircularProgress
              percent={exportPct}
              error={exportError}
              spinning={!exportError && exportPct < 100}
            />
          </div>
        </div>
      )}

      {genProgress && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="laudo-gen-title"
        >
          <div className="w-full max-w-lg rounded-2xl bg-slate-900 p-6 shadow-2xl ring-1 ring-cyan-500/30">
            <div className="mb-5 text-center">
              <h2 id="laudo-gen-title" className="text-base font-semibold text-white">
                Gerando laudo
              </h2>
              <p className="mt-1 text-sm text-slate-400">{genProgress.message || "Processando…"}</p>
            </div>

            <CircularProgress
              percent={genPct}
              error={genProgress.phase === "error"}
              spinning={generating}
            />

            <p className="mt-3 text-center text-xs uppercase tracking-wide text-slate-500">
              Etapa {Math.min(currentStageIdx + 1, GENERATE_STAGES.length)} de {GENERATE_STAGES.length}
              {genProgress.phase !== "done" && genProgress.phase !== "error"
                ? ` · ${GENERATE_STAGES[currentStageIdx]?.label}`
                : ""}
            </p>

            <ol className="mt-5 max-h-64 space-y-1.5 overflow-y-auto">
              {GENERATE_STAGES.map((stage, idx) => {
                const isTerminalDone = genProgress.phase === "done";
                const done = isTerminalDone || idx < currentStageIdx;
                const activeStage =
                  !isTerminalDone &&
                  genProgress.phase !== "error" &&
                  idx === currentStageIdx;
                return (
                  <li
                    key={stage.id}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                      activeStage
                        ? "bg-cyan-500/10 text-cyan-100 ring-1 ring-cyan-500/30"
                        : done
                          ? "text-emerald-300"
                          : "text-slate-500"
                    }`}
                  >
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                        done
                          ? "bg-emerald-500/20 text-emerald-300"
                          : activeStage
                            ? "bg-cyan-500/20 text-cyan-200"
                            : "bg-slate-800 text-slate-500"
                      }`}
                    >
                      {done ? "✓" : idx + 1}
                    </span>
                    <span className={`min-w-0 flex-1 ${activeStage ? "font-medium" : ""}`}>
                      {stage.label}
                    </span>
                    {activeStage && generating && (
                      <span className="shrink-0 text-xs text-cyan-400/80">em andamento…</span>
                    )}
                    {done && !activeStage && (
                      <span className="shrink-0 text-xs text-emerald-400/70">ok</span>
                    )}
                  </li>
                );
              })}
            </ol>

            {generating && genProgress.phase !== "done" && genProgress.phase !== "error" && (
              <button
                type="button"
                onClick={() => void cancelGenerate()}
                className="mt-5 w-full rounded-lg bg-rose-700/80 px-4 py-2 text-sm text-white hover:bg-rose-600"
              >
                Cancelar geração
              </button>
            )}

            {genProgress.phase === "error" && (
              <div className="mt-4 space-y-3">
                <p className="text-sm text-rose-300">
                  A geração falhou. Corrija o problema (anexos, chave Gemini ou prompt) e tente
                  novamente.
                </p>
                <button
                  type="button"
                  onClick={() => setGenProgress(null)}
                  className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white hover:bg-slate-600"
                >
                  Fechar
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <ShellHeader className="px-6" showModelsStatus>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Laudos de Vistoria</h1>
          <p className="text-sm text-slate-500">
            Gemini · templates por tipo · anexos + base de conhecimento · Word/PDF
          </p>
        </div>
        {status && (
          <span
            className={`rounded-full px-3 py-1 text-xs ${
              status.gemini_available
                ? "bg-emerald-500/15 text-emerald-300"
                : "bg-amber-500/15 text-amber-200"
            }`}
          >
            {status.gemini_available
              ? `Gemini OK · ${status.gemini_model}`
              : "Configure GEMINI_API_KEY"}
          </span>
        )}
      </ShellHeader>

      <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-6 lg:flex-row">
        <aside className="w-full shrink-0 space-y-4 lg:w-72">
          <section className="rounded-2xl bg-slate-900/40 p-4 ring-1 ring-slate-800">
            <h2 className="text-sm font-semibold text-white">Laudos recentes</h2>
            <ul className="mt-3 max-h-64 space-y-2 overflow-y-auto text-sm">
              {reports.map((r) => (
                <li key={r.id} className="flex items-stretch gap-1">
                  <button
                    type="button"
                    onClick={() => openReport(r.id)}
                    className={`min-w-0 flex-1 rounded-lg px-3 py-2 text-left hover:bg-slate-800 ${
                      active?.id === r.id ? "bg-slate-800 text-brand-200" : "text-slate-300"
                    }`}
                  >
                    <div className="truncate font-medium">{r.title}</div>
                    <div className="text-xs text-slate-500">
                      {r.status} · {r.template?.name || "sem template"}
                    </div>
                  </button>
                  <button
                    type="button"
                    title="Excluir laudo"
                    onClick={() => removeReport(r.id)}
                    disabled={loading}
                    className="shrink-0 rounded-lg px-2 text-xs text-rose-300 hover:bg-rose-500/20 disabled:opacity-50"
                  >
                    Excluir
                  </button>
                </li>
              ))}
              {!reports.length && (
                <li className="text-xs text-slate-500">Nenhum laudo ainda.</li>
              )}
            </ul>
            <button
              type="button"
              onClick={createDraft}
              disabled={loading}
              className="mt-3 w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50"
            >
              Novo laudo
            </button>
          </section>

          <section className="rounded-2xl bg-slate-900/40 p-4 ring-1 ring-slate-800">
            <h2 className="text-sm font-semibold text-white">Templates</h2>
            <ul className="mt-2 space-y-1 text-xs text-slate-400">
              {templates.map((t) => (
                <li key={t.id}>
                  {t.name} <span className="text-slate-600">({t.slug})</span>
                </li>
              ))}
            </ul>
            <div className="mt-3 flex gap-2">
              <input
                className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white"
                placeholder="Novo tipo de laudo"
                value={newTemplateName}
                onChange={(e) => setNewTemplateName(e.target.value)}
              />
              <button
                type="button"
                onClick={createTemplate}
                className="rounded-lg bg-slate-700 px-3 text-sm text-white"
              >
                +
              </button>
            </div>
          </section>
        </aside>

        <main className="min-w-0 flex-1 space-y-4">
          {error && (
            <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
              {error}
            </div>
          )}

          {!active ? (
            <div className="rounded-2xl bg-slate-900/40 p-8 text-center text-slate-400 ring-1 ring-slate-800">
              Crie um novo laudo ou abra um existente na lista ao lado.
            </div>
          ) : (
            <>
              <section className="space-y-4 rounded-2xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="block text-sm">
                    <span className="text-slate-400">Título</span>
                    <input
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="text-slate-400">Tipo / template</span>
                    <select
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                      value={templateId}
                      onChange={(e) => setTemplateId(e.target.value)}
                    >
                      {templates.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-sm md:col-span-2">
                    <span className="text-slate-400">Projeto vinculado (opcional)</span>
                    <select
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                      value={projectId}
                      onChange={(e) => setProjectId(e.target.value)}
                    >
                      <option value="">— nenhum —</option>
                      {projects.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <fieldset className="space-y-2 text-sm">
                  <legend className="text-slate-400">
                    Consultar base de conhecimento?
                  </legend>
                  <label className="flex items-center gap-2 text-slate-200">
                    <input
                      type="radio"
                      checked={knowledgeMode === "attachments"}
                      onChange={() => setKnowledgeMode("attachments")}
                    />
                    Somente arquivos anexados (PDF, normas, fotos)
                  </label>
                  <label className="flex items-center gap-2 text-slate-200">
                    <input
                      type="radio"
                      checked={knowledgeMode === "attachments_and_kb"}
                      onChange={() => setKnowledgeMode("attachments_and_kb")}
                    />
                    Anexos + base de conhecimento (RAG / NBR)
                  </label>
                </fieldset>

                <label className="block text-sm">
                  <span className="text-slate-400">
                    Prompt / instruções para criar o laudo
                  </span>
                  <textarea
                    className="mt-1 min-h-28 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    placeholder="Descreva o objeto, local, escopo da vistoria, critérios e o que deve constar no laudo…"
                  />
                </label>

                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                  <h3 className="text-sm font-semibold text-white">Solicitante</h3>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Empresa, CNPJ, endereço e contato — incluídos na capa e no corpo do laudo.
                  </p>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {(
                      [
                        ["empresa", "Nome da empresa"],
                        ["cnpj", "CNPJ"],
                        ["endereco", "Endereço"],
                        ["contato", "Contato (telefone / e-mail)"],
                      ] as const
                    ).map(([key, label]) => (
                      <label key={key} className="block text-sm md:col-span-1">
                        <span className="text-slate-400">{label}</span>
                        <input
                          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                          value={solicitante[key] || ""}
                          disabled={loading || generating}
                          onChange={(e) => {
                            const value = e.target.value;
                            setSolicitante((s) => ({ ...s, [key]: value }));
                          }}
                          onBlur={(e) =>
                            persistSolicitante({ ...solicitante, [key]: e.target.value })
                          }
                        />
                      </label>
                    ))}
                  </div>
                  <button
                    type="button"
                    disabled={loading || generating}
                    onClick={() => persistSolicitante(solicitante)}
                    className="mt-3 rounded-lg bg-slate-700 px-3 py-1.5 text-xs text-white hover:bg-slate-600 disabled:opacity-50"
                  >
                    Salvar solicitante
                  </button>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <InspectionPartyList
                      title="Responsáveis técnicos"
                      hint="Aparecem na capa e com assinatura antes do relatório fotográfico."
                      items={responsaveisTecnicos}
                      disabled={loading || generating}
                      showArt
                      onChange={(next) => persistParties(next, responsaveisImagens)}
                    />
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <InspectionPartyList
                      title="Responsáveis pelas imagens"
                      hint="Creditados na apresentação do relatório fotográfico."
                      items={responsaveisImagens}
                      disabled={loading || generating}
                      onChange={(next) => persistParties(responsaveisTecnicos, next)}
                    />
                  </div>
                </div>

                {selectedTemplate && (
                  <p className="text-xs text-slate-500">
                    Capítulos do template:{" "}
                    {(selectedTemplate.chapters || [])
                      .map((c) => c.title)
                      .join(" · ")}
                  </p>
                )}

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={saveMeta}
                    disabled={loading}
                    className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white"
                  >
                    Salvar
                  </button>
                  <button
                    type="button"
                    onClick={generate}
                    disabled={loading || generating}
                    className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50"
                  >
                    {generating ? "Gerando…" : "Gerar laudo (Gemini)"}
                  </button>
                  <button
                    type="button"
                    onClick={() => removeReport(active.id)}
                    disabled={loading}
                    className="rounded-lg bg-rose-700/80 px-4 py-2 text-sm text-white hover:bg-rose-600 disabled:opacity-50"
                  >
                    Excluir laudo
                  </button>
                  {active.content && (
                    <>
                      <button
                        type="button"
                        onClick={() => download("docx")}
                        disabled={loading || generating || !!exporting}
                        className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white disabled:opacity-50"
                      >
                        {exporting === "docx" ? "Exportando Word…" : "Exportar Word"}
                      </button>
                      <button
                        type="button"
                        onClick={() => download("pdf")}
                        disabled={loading || generating || !!exporting}
                        className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white disabled:opacity-50"
                      >
                        {exporting === "pdf" ? "Exportando PDF…" : "Exportar PDF"}
                      </button>
                      <button
                        type="button"
                        onClick={() => download("docx", true)}
                        disabled={loading || generating || !!exporting}
                        className="rounded-lg bg-emerald-800/80 px-4 py-2 text-sm text-white disabled:opacity-50"
                        title="Exige checklist oficial (RT, CNPJ válido, capítulos)"
                      >
                        Word oficial
                      </button>
                      <button
                        type="button"
                        onClick={() => download("pdf", true)}
                        disabled={loading || generating || !!exporting}
                        className="rounded-lg bg-emerald-800/80 px-4 py-2 text-sm text-white disabled:opacity-50"
                        title="Exige checklist oficial (RT, CNPJ válido, capítulos)"
                      >
                        PDF oficial
                      </button>
                    </>
                  )}
                </div>
                {checklist && (
                  <div
                    className={`rounded-lg px-3 py-2 text-xs ${
                      checklist.blocking
                        ? "bg-rose-500/10 text-rose-200"
                        : checklist.ready_for_official_export
                          ? "bg-emerald-500/10 text-emerald-200"
                          : "bg-amber-500/10 text-amber-100"
                    }`}
                  >
                    Checklist exportação:{" "}
                    {checklist.ready_for_official_export
                      ? "pronto para oficial"
                      : checklist.blocking
                        ? checklist.issues.map((i) => i.message).join(" · ")
                        : checklist.warnings.map((w) => w.message).join(" · ") || "revisar avisos"}
                  </div>
                )}
                <p className="text-xs text-slate-500">
                  Status: <strong className="text-slate-300">{active.status}</strong>
                  {active.gemini_model ? ` · modelo ${active.gemini_model}` : ""}
                  {active.error_message ? ` · ${active.error_message}` : ""}
                </p>
              </section>

              <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-2xl bg-slate-900/40 p-4 ring-1 ring-slate-800">
                  <h3 className="text-sm font-semibold text-white">
                    Documentos / normas (PDF)
                  </h3>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.txt,.md,.docx"
                    className="mt-3 block w-full text-sm text-slate-300"
                    onChange={(e) => onUpload(e.target.files, "document")}
                  />
                  <ul className="mt-3 space-y-1 text-xs text-slate-400">
                    {docs.map((a) => (
                      <li key={a.id} className="flex justify-between gap-2">
                        <span className="truncate">{a.filename}</span>
                        <button
                          type="button"
                          className="text-rose-300"
                          onClick={() =>
                            api
                              .deleteInspectionReportAsset(active.id, a.id)
                              .then(() => openReport(active.id))
                          }
                        >
                          remover
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-2xl bg-slate-900/40 p-4 ring-1 ring-slate-800">
                  <h3 className="text-sm font-semibold text-white">
                    Fotos / patologias ({photos.length})
                  </h3>
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    className="mt-3 block w-full text-sm text-slate-300"
                    onChange={(e) => onUpload(e.target.files, "image")}
                  />
                  <ul className="mt-3 space-y-1 text-xs text-slate-400">
                    {photos.map((a) => (
                      <li key={a.id} className="flex justify-between gap-2">
                        <span className="truncate">
                          Foto {String(a.photo_number || "").padStart(2, "0")} — {a.filename}
                          {a.orientation ? ` (${a.orientation})` : ""}
                        </span>
                        <button
                          type="button"
                          className="text-rose-300"
                          onClick={() =>
                            api
                              .deleteInspectionReportAsset(active.id, a.id)
                              .then(() => openReport(active.id))
                          }
                        >
                          remover
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-2xl bg-slate-900/40 p-4 ring-1 ring-slate-800">
                  <h3 className="text-sm font-semibold text-white">
                    Imagem georreferenciada
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Foto com GPS no EXIF. Coordenadas entram na ficha técnica; a imagem
                    fica abaixo da tabela de dados do objeto.
                  </p>
                  <input
                    type="file"
                    accept="image/jpeg,image/jpg,image/tiff,image/png,.jpg,.jpeg,.tif,.tiff"
                    className="mt-3 block w-full text-sm text-slate-300"
                    onChange={(e) => onUpload(e.target.files, "georef")}
                  />
                  {georef ? (
                    <div className="mt-3 space-y-2 text-xs text-slate-300">
                      <div className="overflow-hidden rounded-xl bg-slate-950 ring-1 ring-slate-700">
                        {georefPreviewUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={georefPreviewUrl}
                            alt={georef.filename}
                            className="max-h-56 w-full object-contain bg-slate-950"
                          />
                        ) : (
                          <div className="flex h-40 items-center justify-center text-slate-500">
                            {georefPreviewLoading ? "Carregando preview…" : "Preview indisponível"}
                          </div>
                        )}
                      </div>
                      <p className="truncate font-medium">{georef.filename}</p>
                      <p className="text-slate-400">
                        {georef.gps?.label
                          ? `GPS: ${georef.gps.label}`
                          : georef.caption || "Sem coordenadas EXIF"}
                      </p>
                      <button
                        type="button"
                        className="text-rose-300"
                        onClick={() =>
                          api
                            .deleteInspectionReportAsset(active.id, georef.id)
                            .then(() => openReport(active.id))
                        }
                      >
                        remover
                      </button>
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-slate-500">Nenhuma imagem georref. anexada.</p>
                  )}
                </div>
              </section>

              {active.content && (
                <section className="space-y-3 rounded-2xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
                  <h3 className="text-sm font-semibold text-white">
                    Modo correção — avaliação profissional
                  </h3>
                  <textarea
                    className="min-h-24 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    placeholder="Descreva o que corrigir, incluir ou reescrever no laudo…"
                    value={correction}
                    onChange={(e) => setCorrection(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={applyCorrection}
                    disabled={loading || generating || !correction.trim()}
                    className="rounded-lg bg-amber-600/90 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    {generating ? "Corrigindo…" : "Solicitar correções ao Gemini"}
                  </button>

                  {editChapters.length > 0 && (
                    <div className="space-y-3 rounded-xl border border-slate-700/80 p-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        Editar capítulos (sem re-Gemini)
                      </p>
                      {editChapters.slice(0, 8).map((ch, idx) => (
                        <label key={ch.id || idx} className="block text-xs text-slate-400">
                          {ch.title || ch.id || `Capítulo ${idx + 1}`}
                          <textarea
                            className="mt-1 min-h-16 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white"
                            value={(ch.paragraphs || []).join("\n\n")}
                            onChange={(e) => {
                              const paragraphs = e.target.value
                                .split(/\n\n+/)
                                .map((p) => p.trim())
                                .filter(Boolean);
                              setEditChapters((prev) =>
                                prev.map((c, i) => (i === idx ? { ...c, paragraphs } : c))
                              );
                            }}
                          />
                        </label>
                      ))}
                    </div>
                  )}

                  {editPhotos.length > 0 && (
                    <div className="space-y-2 rounded-xl border border-slate-700/80 p-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        Editar legendas fotográficas
                      </p>
                      {editPhotos.slice(0, 12).map((ph, idx) => (
                        <label key={ph.photo_number || idx} className="block text-xs text-slate-400">
                          Foto {String(ph.photo_number || idx + 1).padStart(2, "0")} — título / legenda
                          <input
                            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white"
                            value={ph.title || ""}
                            onChange={(e) =>
                              setEditPhotos((prev) =>
                                prev.map((p, i) =>
                                  i === idx
                                    ? { ...p, title: e.target.value, legend: e.target.value }
                                    : p
                                )
                              )
                            }
                          />
                        </label>
                      ))}
                    </div>
                  )}

                  {(editChapters.length > 0 || editPhotos.length > 0) && (
                    <button
                      type="button"
                      onClick={() => void saveHumanEdits()}
                      disabled={loading}
                      className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white disabled:opacity-50"
                    >
                      Salvar edição humana
                    </button>
                  )}

                  <pre className="max-h-96 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-300">
                    {JSON.stringify(active.content, null, 2)}
                  </pre>
                </section>
              )}
            </>
          )}
        </main>
      </div>
      <ActionDialogHost />
    </>
  );
}
