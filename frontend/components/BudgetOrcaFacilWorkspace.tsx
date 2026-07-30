"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import ActionDialog from "@/components/ActionDialog";
import LoadingSpinner from "@/components/LoadingSpinner";
import { api } from "@/services/api";
import type {
  BudgetSkeleton,
  OrcaFacilBaseHit,
  OrcaFacilJob,
  OrcaFacilJobSummary,
  OrcaFacilPlanItem,
  OrcaFacilPlanStage,
} from "@/types/api";
import { cn } from "@/lib/utils";

const ORCA_JOB_KEY = "iaserver.orca-facil.jobId";

const DEFAULT_ETAPAS = [
  "ADMINISTRAÇÃO DA OBRA",
  "SERVIÇOS PRELIMINARES",
  "TRABALHOS EM TERRA",
  "DRENAGEM",
  "CONTENÇÕES DE ATERRO",
  "PAISAGISMO",
  "SERVIÇOS FINAIS",
];

const PROMPT_PLACEHOLDER = `Ex.: Obra de contenção e drenagem na Colônia Antônio Aleixo.
Use a planilha exemplo como densidade de serviços.
Quantitativos principais: corte X m³, aterro Y m³, gabião Z m³, TC Ø600 L=… m.
Memórias devem citar prancha FL01/FL02 e mostrar a conta.
Não invente códigos fora da base do modelo.`;

const STATUS_LABEL: Record<string, string> = {
  created: "Rascunho",
  running: "Gerando…",
  ready: "Pronto",
  error: "Erro",
};

type Props = {
  onError: (err: unknown, title?: string) => void;
  onSuccess: (message: string, title?: string) => void;
};

type ConfirmState = {
  open: boolean;
  title: string;
  message: string;
  onConfirm?: () => void | Promise<void>;
};

function persistJobId(jobId: string | null) {
  try {
    if (!jobId) sessionStorage.removeItem(ORCA_JOB_KEY);
    else sessionStorage.setItem(ORCA_JOB_KEY, jobId);
  } catch {
    /* ignore */
  }
}

function readJobId(): string | null {
  try {
    return sessionStorage.getItem(ORCA_JOB_KEY);
  } catch {
    return null;
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function cloneStages(stages: OrcaFacilPlanStage[] | undefined | null): OrcaFacilPlanStage[] {
  return JSON.parse(JSON.stringify(stages || [])) as OrcaFacilPlanStage[];
}

function fmtBRL(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Paridade Excel TRUNC(x, 2). */
function trunc2(v: number): number {
  return v < 0 ? Math.ceil(v * 100) / 100 : Math.floor(v * 100) / 100;
}

/** Paridade PLANILHA: TRUNC(PU*(1+BDI),2) → TRUNC(qtd*PU_BDI,2). */
function lineTotalWithBdi(qty: number, unitPrice: number, bdiRate: number): number {
  const puBdi = trunc2(unitPrice * (1 + bdiRate));
  return trunc2(qty * puBdi);
}

const OBRA_BDI: Record<string, { comd: number; semd: number }> = {
  ED: { comd: 0.2572, semd: 0.2212 },
  RF: { comd: 0.2426, semd: 0.2097 },
  FIE: { comd: 0.1738, semd: 0.1402 },
  IE: { comd: 0.2889, semd: 0.252 },
  OPMF: { comd: 0.3123, semd: 0.252 },
  SEE: { comd: 0.0, semd: 0.1772 },
  AG: { comd: 0.2788, semd: 0.2418 },
};

function bdiRatesFor(obraType: string | null | undefined, preview?: { bdi_rate_comd?: number; bdi_rate_semd?: number } | null) {
  if (preview?.bdi_rate_comd != null && preview?.bdi_rate_semd != null) {
    return { comd: preview.bdi_rate_comd, semd: preview.bdi_rate_semd };
  }
  const key = String(obraType || "ED").toUpperCase();
  return OBRA_BDI[key] || OBRA_BDI.ED;
}

function stageSubtotals(
  items: OrcaFacilPlanItem[] | undefined,
  bdi: { comd: number; semd: number }
) {
  let comd = 0;
  let semd = 0;
  for (const it of items || []) {
    const qty = typeof it.qty === "number" ? it.qty : parseFloat(String(it.qty || "0")) || 0;
    if (it.price_comd != null) comd += lineTotalWithBdi(qty, it.price_comd, bdi.comd);
    if (it.price_semd != null) semd += lineTotalWithBdi(qty, it.price_semd, bdi.semd);
  }
  return { comd, semd };
}

function skeletonToEtapasText(sk: BudgetSkeleton): string {
  return sk.etapas.map((e) => e.name).join("\n");
}

function skeletonToEtapasSeed(sk: BudgetSkeleton) {
  return sk.etapas.map((e) => ({
    name: e.name,
    subetapas: (e.sub_etapas || []).map((s) => ({ name: s.name })),
  }));
}

function formatJobDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function BudgetOrcaFacilWorkspace({ onError, onSuccess }: Props) {
  const [job, setJob] = useState<OrcaFacilJob | null>(null);
  const [jobList, setJobList] = useState<OrcaFacilJobSummary[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [skeletons, setSkeletons] = useState<BudgetSkeleton[]>([]);
  const [selectedSkeletonId, setSelectedSkeletonId] = useState("");
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState("OrçaFacil");
  const [userPrompt, setUserPrompt] = useState("");
  const [etapasText, setEtapasText] = useState(DEFAULT_ETAPAS.join("\n"));
  const [prazo, setPrazo] = useState(6);
  const [dmt, setDmt] = useState(30);
  const [empol, setEmpol] = useState(1.3);
  const [obraType, setObraType] = useState("ED");
  const [modeloName, setModeloName] = useState<string | null>(null);
  const [exemploName, setExemploName] = useState<string | null>(null);
  const [pranchaNames, setPranchaNames] = useState<string[]>([]);
  const [fotoNames, setFotoNames] = useState<string[]>([]);
  const [editStages, setEditStages] = useState<OrcaFacilPlanStage[]>([]);
  const [expandedStage, setExpandedStage] = useState<number | null>(0);
  const [dirtyPlan, setDirtyPlan] = useState(false);
  const [basePickerStage, setBasePickerStage] = useState<number | null>(null);
  const [itemPickerKey, setItemPickerKey] = useState<string | null>(null); // "si-ii"
  const [baseQuery, setBaseQuery] = useState("");
  const [baseHits, setBaseHits] = useState<OrcaFacilBaseHit[]>([]);
  const [baseSearching, setBaseSearching] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmState>({
    open: false,
    title: "",
    message: "",
  });

  const etapasSeed = useMemo(
    () =>
      etapasText
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((name) => ({ name })),
    [etapasText]
  );

  const refreshJobList = useCallback(async () => {
    setListLoading(true);
    try {
      const res = await api.orcaFacilListJobs(80, true);
      setJobList((res.jobs || []) as OrcaFacilJobSummary[]);
    } catch {
      setJobList([]);
    } finally {
      setListLoading(false);
    }
  }, []);

  const applyJob = useCallback((j: OrcaFacilJob) => {
    setJob(j);
    persistJobId(j.id);
    const modelo = j.files?.modelo;
    if (modelo) setModeloName(modelo.split(/[/\\]/).pop() || modelo);
    else setModeloName(null);
    const exemplo = j.files?.exemplo;
    if (exemplo) setExemploName(exemplo.split(/[/\\]/).pop() || exemplo);
    else setExemploName(null);
    if (j.title) setTitle(j.title);
    if (typeof j.user_prompt === "string") setUserPrompt(j.user_prompt);
    if (j.skeleton_id) setSelectedSkeletonId(j.skeleton_id);
    const prem = j.premissas || {};
    if (prem.prazo_meses != null) setPrazo(Number(prem.prazo_meses) || 6);
    if (prem.dmt_jazida_km != null) setDmt(Number(prem.dmt_jazida_km) || 30);
    if (prem.empolamento != null) setEmpol(Number(prem.empolamento) || 1.3);
    if (prem.obra_type) setObraType(String(prem.obra_type));
    if (j.etapas_seed?.length) {
      setEtapasText(j.etapas_seed.map((e) => e.name).join("\n"));
    }
    setPranchaNames((j.files?.pranchas || []).map((p) => p.split(/[/\\]/).pop() || p));
    setFotoNames((j.files?.fotos || []).map((p) => p.split(/[/\\]/).pop() || p));
  }, []);

  const loadJob = useCallback(
    async (jobId: string) => {
      setBusy(true);
      try {
        const j = await api.orcaFacilGetJob(jobId);
        setDirtyPlan(false);
        applyJob(j);
        setEditStages(cloneStages(j.plan?.stages));
        setExpandedStage(0);
        await refreshJobList();
      } catch (err) {
        onError(err, "Carregar orçamento");
      } finally {
        setBusy(false);
      }
    },
    [applyJob, refreshJobList, onError]
  );

  const handleNewBudget = useCallback(() => {
    setJob(null);
    persistJobId(null);
    setTitle("OrçaFacil");
    setUserPrompt("");
    setEtapasText(DEFAULT_ETAPAS.join("\n"));
    setPrazo(6);
    setDmt(30);
    setEmpol(1.3);
    setObraType("ED");
    setModeloName(null);
    setExemploName(null);
    setPranchaNames([]);
    setFotoNames([]);
    setEditStages([]);
    setDirtyPlan(false);
    setSelectedSkeletonId("");
    setExpandedStage(0);
    setBasePickerStage(null);
    setBaseQuery("");
    setBaseHits([]);
  }, []);

  const handleDeleteJob = useCallback(
    (item: OrcaFacilJobSummary) => {
      setConfirm({
        open: true,
        title: "Excluir orçamento",
        message: `Remover "${item.title}"?\n\nTodos os arquivos e a planilha gerada deste job serão apagados. Esta ação não pode ser desfeita.`,
        onConfirm: async () => {
          setBusy(true);
          try {
            await api.orcaFacilDeleteJob(item.id);
            if (job?.id === item.id) handleNewBudget();
            await refreshJobList();
            onSuccess("Orçamento excluído", "OrçaFacil");
          } catch (err) {
            onError(err, "Excluir orçamento");
          } finally {
            setBusy(false);
          }
        },
      });
    },
    [job?.id, handleNewBudget, refreshJobList, onError, onSuccess]
  );

  const pollJob = useCallback(
    async (jobId: string) => {
      for (let i = 0; i < 240; i++) {
        const j = await api.orcaFacilGetJob(jobId);
        setDirtyPlan(false);
        applyJob({ ...j });
        setEditStages(cloneStages(j.plan?.stages));
        if (j.status === "ready" || j.status === "error") return j;
        await new Promise((r) => setTimeout(r, 1200));
      }
      throw new Error("Timeout aguardando OrçaFacil");
    },
    [applyJob]
  );

  const metaBody = useCallback(() => {
    const sk = skeletons.find((s) => s.id === selectedSkeletonId);
    return {
      title,
      user_prompt: userPrompt,
      premissas: {
        prazo_meses: prazo,
        dmt_jazida_km: dmt,
        dmt_bota_km: dmt,
        empolamento: empol,
        obra_type: obraType,
      },
      etapas_seed: sk ? skeletonToEtapasSeed(sk) : etapasSeed,
      skeleton_id: selectedSkeletonId || null,
      skeleton_name: sk?.name || null,
    };
  }, [
    title,
    userPrompt,
    prazo,
    dmt,
    empol,
    obraType,
    etapasSeed,
    selectedSkeletonId,
    skeletons,
  ]);

  const ensureJob = useCallback(async () => {
    if (job?.id) return job;
    const created = await api.orcaFacilCreateJob(metaBody());
    applyJob(created);
    await refreshJobList();
    return created;
  }, [job, metaBody, applyJob, refreshJobList]);

  const upload = useCallback(
    async (kind: "modelo" | "exemplo" | "pranchas" | "fotos", fileList: FileList | null) => {
      if (!fileList?.length) return;
      setBusy(true);
      try {
        const j = await ensureJob();
        const files = Array.from(fileList);
        const res = await api.orcaFacilUpload(j.id, kind, files);
        applyJob(res.job);
        if (kind === "modelo") setModeloName(files[0]?.name || null);
        if (kind === "exemplo") setExemploName(files[0]?.name || null);
        if (kind === "pranchas") setPranchaNames(files.map((f) => f.name));
        if (kind === "fotos") setFotoNames(files.map((f) => f.name));
        onSuccess(`${files.length} arquivo(s) enviado(s) (${kind})`, "OrçaFacil");
      } catch (err) {
        onError(err, "Upload OrçaFacil");
      } finally {
        setBusy(false);
      }
    },
    [ensureJob, applyJob, onError, onSuccess]
  );

  const syncMeta = useCallback(async () => {
    if (!job?.id) return;
    const updated = await api.orcaFacilUpdateJob(job.id, metaBody());
    applyJob(updated);
  }, [job?.id, metaBody, applyJob]);

  const run = useCallback(async () => {
    setBusy(true);
    try {
      let j = await ensureJob();
      await api.orcaFacilUpdateJob(j.id, metaBody());
      j = await api.orcaFacilProcess(j.id, true);
      applyJob(j);
      const done = await pollJob(j.id);
      await refreshJobList();
      if (done.status === "error") {
        throw new Error(done.error || "Falha no OrçaFacil");
      }
      setDirtyPlan(false);
      setEditStages(cloneStages(done.plan?.stages));
      const n = done.preview?.workbook_n_servicos ?? done.preview?.n_services ?? "?";
      onSuccess(
        `Gerado: ${done.preview?.n_etapas ?? "?"} etapas · ${n} serviços. Revise no editor MCQ.`,
        "OrçaFacil"
      );
    } catch (err) {
      onError(err, "Gerar OrçaFacil");
    } finally {
      setBusy(false);
    }
  }, [ensureJob, metaBody, pollJob, applyJob, refreshJobList, onError, onSuccess]);

  const exportXlsm = useCallback(async () => {
    if (!job?.id) return;
    setBusy(true);
    try {
      if (dirtyPlan) {
        const saved = await api.orcaFacilPutPlan(job.id, {
          stages: editStages,
          rewrite_workbook: true,
        });
        applyJob(saved);
        setDirtyPlan(false);
      }
      const blob = await api.orcaFacilExportXlsm(job.id);
      const name = (job.title || "OrcaFacil").replace(/\s+/g, "_").slice(0, 40);
      downloadBlob(blob, `${name}_MODELO.xlsm`);
      onSuccess("Download da planilha modelo iniciado", "Exportar");
    } catch (err) {
      onError(err, "Exportar .xlsm");
    } finally {
      setBusy(false);
    }
  }, [job, dirtyPlan, editStages, applyJob, onError, onSuccess]);

  const savePlan = useCallback(async () => {
    if (!job?.id) return;
    setBusy(true);
    try {
      const saved = await api.orcaFacilPutPlan(job.id, {
        stages: editStages,
        rewrite_workbook: true,
      });
      setDirtyPlan(false);
      applyJob(saved);
      await refreshJobList();
      onSuccess(
        `MCQ salva · ${saved.workbook_stats?.n_servicos ?? "?"} serviços regravados no modelo`,
        "Editor MCQ"
      );
    } catch (err) {
      onError(err, "Salvar MCQ");
    } finally {
      setBusy(false);
    }
  }, [job?.id, editStages, applyJob, refreshJobList, onError, onSuccess]);

  const updateItem = useCallback(
    (si: number, ii: number, patch: Partial<OrcaFacilPlanItem>) => {
      setEditStages((prev) => {
        const next = cloneStages(prev);
        const items = next[si]?.items || [];
        items[ii] = { ...items[ii], ...patch };
        next[si] = { ...next[si], items };
        return next;
      });
      setDirtyPlan(true);
    },
    []
  );

  const addFromBase = useCallback((si: number, hit: OrcaFacilBaseHit) => {
    setEditStages((prev) => {
      const next = cloneStages(prev);
      const items = [
        ...(next[si]?.items || []),
        {
          code: hit.code,
          description: hit.description,
          unit: hit.unit || "UN",
          qty: 1,
          qty_basis: "base_modelo",
          memory: `${hit.description}\nConforme base do modelo\nQtd = 1 ${hit.unit || "UN"}\nTotal = 1 ${hit.unit || "UN"}`,
          needs_match: false,
          confidence: 1,
          price_comd: hit.price_comd ?? null,
          price_semd: hit.price_semd ?? null,
        },
      ];
      next[si] = { ...next[si], items };
      return next;
    });
    setDirtyPlan(true);
    setBasePickerStage(null);
    setBaseQuery("");
    setBaseHits([]);
    setExpandedStage(si);
  }, []);

  const replaceFromBase = useCallback(
    (si: number, ii: number, hit: OrcaFacilBaseHit) => {
      updateItem(si, ii, {
        code: hit.code,
        description: hit.description,
        unit: hit.unit || "UN",
        price_comd: hit.price_comd ?? null,
        price_semd: hit.price_semd ?? null,
        needs_match: false,
        confidence: 1,
      });
      setItemPickerKey(null);
      setBaseQuery("");
      setBaseHits([]);
    },
    [updateItem]
  );

  const removeItem = useCallback((si: number, ii: number) => {
    setEditStages((prev) => {
      const next = cloneStages(prev);
      const items = [...(next[si]?.items || [])];
      items.splice(ii, 1);
      next[si] = { ...next[si], items };
      return next;
    });
    setDirtyPlan(true);
  }, []);

  const addStage = useCallback(() => {
    const name = window.prompt("Nome da etapa:");
    if (!name?.trim()) return;
    setEditStages((prev) => [...cloneStages(prev), { name: name.trim(), items: [], subetapas: [] }]);
    setDirtyPlan(true);
  }, []);

  const removeStage = useCallback((si: number) => {
    setConfirm({
      open: true,
      title: "Remover etapa",
      message: "Remover esta etapa e todos os serviços associados?",
      onConfirm: () => {
        setEditStages((prev) => {
          const next = cloneStages(prev);
          next.splice(si, 1);
          return next;
        });
        setDirtyPlan(true);
      },
    });
  }, []);

  const applySkeleton = useCallback(
    (skeletonId: string) => {
      setSelectedSkeletonId(skeletonId);
      if (!skeletonId) return;
      const sk = skeletons.find((s) => s.id === skeletonId);
      if (!sk) return;
      setEtapasText(skeletonToEtapasText(sk));
      setObraType(sk.obra_type || "ED");
      if (!job?.id || title === "OrçaFacil") setTitle(sk.name);
    },
    [skeletons, job?.id, title]
  );

  useEffect(() => {
    void refreshJobList();
    api.pricingListSkeletons().then((r) => setSkeletons(r.items || [])).catch(() => {});
  }, [refreshJobList]);

  useEffect(() => {
    const boot = async () => {
      const stored = readJobId();
      try {
        if (stored) {
          await loadJob(stored);
          return;
        }
      } catch {
        /* ignore */
      }
    };
    void boot();
  }, [loadJob]);

  useEffect(() => {
    const hasPicker = basePickerStage !== null || itemPickerKey !== null;
    if (!hasPicker || !job?.id || baseQuery.trim().length < 1) {
      setBaseHits([]);
      return;
    }
    const t = window.setTimeout(() => {
      setBaseSearching(true);
      api
        .orcaFacilSearchBase(job.id, baseQuery.trim(), 25)
        .then((r) => setBaseHits(r.hits || []))
        .catch(() => setBaseHits([]))
        .finally(() => setBaseSearching(false));
    }, 280);
    return () => window.clearTimeout(t);
  }, [baseQuery, basePickerStage, itemPickerKey, job?.id]);

  const progress = job?.progress ?? 0;
  const canExport = Boolean(
    job?.status === "ready" && (job.workbook_path || job.session_id || dirtyPlan)
  );
  const hasModelo = Boolean(modeloName || job?.files?.modelo);
  const showEditor = Boolean(job?.status === "ready" && (editStages.length > 0 || job.plan));
  const bdi = bdiRatesFor(obraType, job?.preview);

  return (
    <>
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden md:flex-row">
        {/* Sidebar — orçamentos salvos */}
        <aside className="flex w-full shrink-0 flex-col md:w-80 lg:w-96">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Orçamentos salvos
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={handleNewBudget}
              className="text-xs font-medium text-brand-400 hover:text-brand-300"
            >
              + Novo
            </button>
          </div>
          <div className="app-card min-h-[180px] max-h-[40vh] flex-1 overflow-y-auto p-2 md:max-h-none">
            {listLoading ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="sm" label="Carregando..." />
              </div>
            ) : jobList.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-slate-500">
                Nenhum orçamento ainda. Clique em <strong>+ Novo</strong>.
              </p>
            ) : (
              <ul className="space-y-1">
                {jobList.map((item) => (
                  <li
                    key={item.id}
                    className={cn(
                      "rounded-lg border px-2.5 py-2 transition-colors",
                      job?.id === item.id
                        ? "border-brand-500/40 bg-brand-500/10"
                        : "border-transparent hover:bg-white/5"
                    )}
                  >
                    <button
                      type="button"
                      className="w-full text-left"
                      onClick={() => void loadJob(item.id)}
                    >
                      <p className="truncate text-sm font-medium text-slate-100">{item.title}</p>
                      <p className="text-[10px] text-slate-500">
                        {STATUS_LABEL[item.status] || item.status}
                        {item.n_services != null ? ` · ${item.n_services} serv.` : ""}
                        {item.has_workbook ? " · .xlsm" : ""}
                      </p>
                      {(item.total_comd != null || item.total_semd != null) && (
                        <div className="mt-1 space-y-0.5 font-mono text-[10px] leading-tight">
                          <p className="text-emerald-300">
                            ComD c/BDI R$ {fmtBRL(item.total_comd)}
                          </p>
                          <p className="text-slate-400">
                            SemD c/BDI R$ {fmtBRL(item.total_semd)}
                          </p>
                        </div>
                      )}
                      <p className="mt-0.5 text-[10px] text-slate-600">{formatJobDate(item.updated_at)}</p>
                    </button>
                    <div className="mt-1.5 flex gap-2">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void loadJob(item.id)}
                        className="text-[11px] text-brand-300 hover:text-brand-200"
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => handleDeleteJob(item)}
                        className="text-[11px] text-rose-400 hover:text-rose-300"
                      >
                        Excluir
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Link
            href="/budget/models"
            className="mt-3 block rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-center text-xs text-slate-400 hover:bg-white/10 hover:text-slate-200"
          >
            Cadastrar modelos WBS
          </Link>
        </aside>

        {/* Área principal — ocupa toda a largura restante */}
        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto pb-8">
          <div className="flex w-full flex-col gap-4">
            <section className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
              <h2 className="text-sm font-semibold text-white">1. Planilha modelo (obrigatória)</h2>
              <p className="mt-1 text-xs text-slate-400">
                Base de preços embutida — a saída é cópia deste arquivo com MCQ preenchida.
              </p>
              <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg bg-brand-500/20 px-3 py-2 text-xs text-brand-100 hover:bg-brand-500/30">
                <input
                  type="file"
                  accept=".xlsm,.xlsx"
                  className="hidden"
                  disabled={busy}
                  onChange={(e) => upload("modelo", e.target.files)}
                />
                Escolher modelo .xlsm
              </label>
              {modeloName && <p className="mt-2 text-xs text-emerald-300">Modelo: {modeloName}</p>}
              {job?.base_summary?.size ? (
                <p className="mt-1 text-xs text-slate-400">
                  Base indexada: {job.base_summary.sheet_name} · {job.base_summary.size} itens
                </p>
              ) : null}
            </section>

            <section className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
              <h2 className="text-sm font-semibold text-white">2. Pranchas, fotos e exemplo</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-200 hover:bg-white/10">
                  <input
                    type="file"
                    accept=".pdf,image/*"
                    multiple
                    className="hidden"
                    disabled={busy}
                    onChange={(e) => upload("pranchas", e.target.files)}
                  />
                  Pranchas PDF
                </label>
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-200 hover:bg-white/10">
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    disabled={busy}
                    onChange={(e) => upload("fotos", e.target.files)}
                  />
                  Fotos
                </label>
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-emerald-500/15 px-3 py-2 text-xs text-emerald-100 hover:bg-emerald-500/25">
                  <input
                    type="file"
                    accept=".xlsm,.xlsx"
                    className="hidden"
                    disabled={busy}
                    onChange={(e) => upload("exemplo", e.target.files)}
                  />
                  Exemplo .xlsm
                </label>
              </div>
              {(pranchaNames.length > 0 || fotoNames.length > 0 || exemploName) && (
                <div className="mt-2 space-y-0.5 text-xs text-slate-400">
                  {pranchaNames.length > 0 && <p>Pranchas: {pranchaNames.join(", ")}</p>}
                  {fotoNames.length > 0 && <p>Fotos: {fotoNames.join(", ")}</p>}
                  {exemploName && <p className="text-emerald-300">Exemplo: {exemploName}</p>}
                </div>
              )}
            </section>

            <section className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
              <h2 className="text-sm font-semibold text-white">3. Prompt do engenheiro</h2>
              <textarea
                className="mt-3 h-28 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-600"
                placeholder={PROMPT_PLACEHOLDER}
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                onBlur={() => void syncMeta()}
              />
            </section>

            <section className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
              <h2 className="text-sm font-semibold text-white">4. Modelo WBS + etapas</h2>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-slate-500">Modelo de orçamento (WBS)</label>
                    <select
                      className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
                      value={selectedSkeletonId}
                      disabled={busy}
                      onChange={(e) => {
                        applySkeleton(e.target.value);
                        void syncMeta();
                      }}
                    >
                      <option value="">— Selecionar modelo cadastrado —</option>
                      {skeletons.map((sk) => (
                        <option key={sk.id} value={sk.id}>
                          {sk.name} ({sk.etapas.length} etapas · {sk.obra_type})
                        </option>
                      ))}
                    </select>
                    <p className="mt-1 text-[10px] text-slate-500">
                      Modelos em{" "}
                      <Link href="/budget/models" className="text-brand-400 hover:underline">
                        Cadastrar modelo de orçamento
                      </Link>
                    </p>
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Título do orçamento</label>
                    <input
                      className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      onBlur={() => void syncMeta()}
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Etapas (1 por linha)</label>
                  <textarea
                    className="mt-1 h-40 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 font-mono text-xs text-white"
                    value={etapasText}
                    onChange={(e) => setEtapasText(e.target.value)}
                    onBlur={() => void syncMeta()}
                  />
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                <div>
                  <label className="text-xs text-slate-500">Prazo (meses)</label>
                  <input
                    type="number"
                    className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
                    value={prazo}
                    onChange={(e) => setPrazo(Number(e.target.value) || 0)}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">DMT (km)</label>
                  <input
                    type="number"
                    className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
                    value={dmt}
                    onChange={(e) => setDmt(Number(e.target.value) || 0)}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Empolamento</label>
                  <input
                    type="number"
                    step="0.01"
                    className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
                    value={empol}
                    onChange={(e) => setEmpol(Number(e.target.value) || 1)}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">obra_type</label>
                  <input
                    className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
                    value={obraType}
                    onChange={(e) => setObraType(e.target.value.toUpperCase())}
                  />
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={busy || !hasModelo}
                  onClick={() => void run()}
                  className={cn(
                    "rounded-lg px-4 py-2 text-sm font-medium",
                    busy || !hasModelo
                      ? "cursor-not-allowed bg-slate-700 text-slate-400"
                      : "bg-brand-500 text-white hover:bg-brand-400"
                  )}
                >
                  {busy ? "Gerando…" : "Gerar orçamento (Gemini 3.6)"}
                </button>
                <button
                  type="button"
                  disabled={!canExport || busy}
                  onClick={() => void exportXlsm()}
                  className={cn(
                    "rounded-lg px-4 py-2 text-sm font-medium",
                    canExport
                      ? "bg-emerald-600 text-white hover:bg-emerald-500"
                      : "cursor-not-allowed bg-slate-800 text-slate-500"
                  )}
                >
                  Baixar planilha modelo
                </button>
              </div>

              {(job?.status === "running" || (progress > 0 && job?.status !== "ready")) && (
                <div className="mt-4">
                  <div className="mb-1 flex justify-between text-xs text-slate-400">
                    <span>{job?.message || job?.phase}</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full bg-brand-500 transition-all"
                      style={{ width: `${Math.min(100, progress)}%` }}
                    />
                  </div>
                </div>
              )}

              {job?.warnings && job.warnings.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-300">
                  {job.warnings.slice(0, 8).map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
              {job?.error && <p className="mt-3 text-xs text-rose-400">{job.error}</p>}
            </section>

            {showEditor && (
              <section className="rounded-xl border border-emerald-500/25 bg-slate-900/50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-white">5. Editor MCQ</h2>
                    <p className="mt-1 text-xs text-slate-400">
                      Busque composições na base do modelo por código ou descrição.
                    </p>
                    {(() => {
                      let totalComd = 0, totalSemd = 0;
                      for (const s of editStages) {
                        const sub = stageSubtotals(s.items, bdi);
                        totalComd += sub.comd;
                        totalSemd += sub.semd;
                      }
                      return (
                        <div className="mt-1 space-y-0.5 font-mono text-xs leading-tight">
                          <p className="text-emerald-300">
                            Total ComD c/ BDI {(bdi.comd * 100).toFixed(2).replace(".", ",")}%: R${" "}
                            {fmtBRL(totalComd)}
                          </p>
                          <p className="text-slate-400">
                            Total SemD c/ BDI {(bdi.semd * 100).toFixed(2).replace(".", ",")}%: R${" "}
                            {fmtBRL(totalSemd)}
                          </p>
                        </div>
                      );
                    })()}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={addStage}
                      className="rounded-lg bg-white/10 px-3 py-1.5 text-xs text-white hover:bg-white/15"
                    >
                      + Etapa
                    </button>
                    <button
                      type="button"
                      disabled={busy || !dirtyPlan}
                      onClick={() => void savePlan()}
                      className={cn(
                        "rounded-lg px-3 py-1.5 text-xs font-medium",
                        dirtyPlan
                          ? "bg-brand-500 text-white hover:bg-brand-400"
                          : "cursor-not-allowed bg-slate-800 text-slate-500"
                      )}
                    >
                      {dirtyPlan ? "Salvar MCQ no modelo" : "MCQ salva"}
                    </button>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  {editStages.map((st, si) => {
                    const n = st.items?.length ?? 0;
                    const open = expandedStage === si;
                    const pickerOpen = basePickerStage === si;
                    const sub = stageSubtotals(st.items, bdi);
                    return (
                      <div
                        key={`${st.name}-${si}`}
                        className="rounded-lg border border-white/10 bg-slate-950/50"
                      >
                        <div className="flex flex-wrap items-center gap-2 px-3 py-2">
                          <button
                            type="button"
                            className="min-w-0 flex-1 text-left text-sm font-medium text-slate-100"
                            onClick={() => setExpandedStage(open ? null : si)}
                          >
                            {open ? "▾" : "▸"} {st.name || `Etapa ${si + 1}`}{" "}
                            <span className="font-normal text-slate-500">· {n} serv.</span>
                          </button>
                          <div className="shrink-0 text-right font-mono text-[10px] leading-tight">
                            <p className="text-emerald-300">ComD c/BDI R$ {fmtBRL(sub.comd)}</p>
                            <p className="text-slate-400">SemD c/BDI R$ {fmtBRL(sub.semd)}</p>
                          </div>
                          <button
                            type="button"
                            disabled={!hasModelo}
                            className="text-[11px] text-emerald-300 hover:text-emerald-200 disabled:text-slate-600"
                            onClick={() => {
                              setExpandedStage(si);
                              setBasePickerStage(pickerOpen ? null : si);
                              setItemPickerKey(null);
                              setBaseQuery("");
                              setBaseHits([]);
                            }}
                          >
                            Buscar na base
                          </button>
                          <button
                            type="button"
                            className="text-[11px] text-rose-300 hover:text-rose-200"
                            onClick={() => removeStage(si)}
                          >
                            remover
                          </button>
                        </div>

                        {open && pickerOpen && (
                          <div className="border-t border-white/5 bg-slate-900/60 p-3">
                            <label className="text-[10px] uppercase text-slate-500">
                              Adicionar composição da base (código ou descrição)
                            </label>
                            <input
                              autoFocus
                              className="mt-1 w-full rounded border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
                              placeholder="Ex.: 92212, gabião, tubo concreto 600…"
                              value={baseQuery}
                              onChange={(e) => setBaseQuery(e.target.value)}
                            />
                            {baseSearching && (
                              <p className="mt-2 text-xs text-slate-500">Buscando na base…</p>
                            )}
                            {!baseSearching && baseQuery.trim() && baseHits.length === 0 && (
                              <p className="mt-2 text-xs text-slate-500">Nenhuma composição encontrada.</p>
                            )}
                            <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto">
                              {baseHits.map((hit) => (
                                <li key={`${hit.code}-${hit.score}`}>
                                  <button
                                    type="button"
                                    className="w-full rounded-md border border-white/5 bg-slate-950/80 px-3 py-2 text-left hover:border-brand-500/30 hover:bg-brand-500/5"
                                    onClick={() => addFromBase(si, hit)}
                                  >
                                    <span className="font-mono text-xs text-brand-200">{hit.code}</span>
                                    <span className="ml-2 text-[10px] text-slate-500">{hit.unit}</span>
                                    <span className="ml-2 text-[10px] text-emerald-400">
                                      R$ {fmtBRL(hit.price_comd)}
                                    </span>
                                    <span className="ml-1 text-[10px] text-slate-500">
                                      / SemD {fmtBRL(hit.price_semd)}
                                    </span>
                                    <p className="mt-0.5 line-clamp-2 text-xs text-slate-300">
                                      {hit.description}
                                    </p>
                                  </button>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {open && (
                          <div className="space-y-3 border-t border-white/5 p-3">
                            {(st.items || []).map((it, ii) => {
                              const iKey = `${si}-${ii}`;
                              const iPicker = itemPickerKey === iKey;
                              const qty = typeof it.qty === "number" ? it.qty : parseFloat(String(it.qty || "0")) || 0;
                              return (
                                <div
                                  key={ii}
                                  className="rounded-md border border-white/5 bg-slate-900/80 p-3"
                                >
                                  <div className="grid gap-2 md:grid-cols-8">
                                    <div className="md:col-span-1">
                                      <label className="text-[10px] uppercase text-slate-500">Código</label>
                                      <input
                                        className="mt-0.5 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 font-mono text-xs text-white"
                                        value={it.code ?? ""}
                                        onChange={(e) => updateItem(si, ii, { code: e.target.value })}
                                      />
                                    </div>
                                    <div className="md:col-span-2">
                                      <label className="text-[10px] uppercase text-slate-500">Descrição</label>
                                      <input
                                        className="mt-0.5 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-xs text-white"
                                        value={it.description ?? ""}
                                        onChange={(e) =>
                                          updateItem(si, ii, { description: e.target.value })
                                        }
                                      />
                                    </div>
                                    <div>
                                      <label className="text-[10px] uppercase text-slate-500">Un</label>
                                      <input
                                        className="mt-0.5 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-xs text-white"
                                        value={it.unit ?? ""}
                                        onChange={(e) => updateItem(si, ii, { unit: e.target.value })}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-[10px] uppercase text-slate-500">Qtd</label>
                                      <input
                                        type="number"
                                        className="mt-0.5 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 text-xs text-white"
                                        value={it.qty ?? ""}
                                        onChange={(e) =>
                                          updateItem(si, ii, {
                                            qty: e.target.value === "" ? "" : Number(e.target.value),
                                          })
                                        }
                                      />
                                    </div>
                                    <div>
                                      <label className="text-[10px] uppercase text-slate-500">PU ComD</label>
                                      <input
                                        readOnly
                                        className="mt-0.5 w-full rounded border border-white/10 bg-slate-950/80 px-2 py-1.5 font-mono text-xs text-emerald-300"
                                        value={fmtBRL(it.price_comd)}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-[10px] uppercase text-slate-500">PU SemD</label>
                                      <input
                                        readOnly
                                        className="mt-0.5 w-full rounded border border-white/10 bg-slate-950/80 px-2 py-1.5 font-mono text-xs text-slate-300"
                                        value={fmtBRL(it.price_semd)}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-[10px] uppercase text-slate-500">Subt. c/ BDI</label>
                                      <input
                                        readOnly
                                        className="mt-0.5 w-full rounded border border-white/10 bg-slate-950/80 px-2 py-1.5 font-mono text-xs text-emerald-300"
                                        value={
                                          it.price_comd != null
                                            ? fmtBRL(lineTotalWithBdi(qty, it.price_comd, bdi.comd))
                                            : "—"
                                        }
                                      />
                                    </div>
                                  </div>
                                  <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-slate-400">
                                    {it.price_semd != null && (
                                      <span>
                                        Subt. SemD c/ BDI: R${" "}
                                        {fmtBRL(lineTotalWithBdi(qty, it.price_semd, bdi.semd))}
                                      </span>
                                    )}
                                    <button
                                      type="button"
                                      disabled={!hasModelo}
                                      className="text-emerald-300 hover:text-emerald-200 disabled:text-slate-600"
                                      onClick={() => {
                                        setBasePickerStage(null);
                                        setItemPickerKey(iPicker ? null : iKey);
                                        setBaseQuery(it.description?.slice(0, 40) || "");
                                        setBaseHits([]);
                                      }}
                                    >
                                      {iPicker ? "Fechar busca" : "Buscar composição"}
                                    </button>
                                  </div>
                                  {iPicker && (
                                    <div className="mt-2 rounded border border-white/5 bg-slate-900/60 p-2">
                                      <input
                                        autoFocus
                                        className="w-full rounded border border-white/10 bg-slate-950 px-3 py-1.5 text-xs text-white"
                                        placeholder="Código ou descrição…"
                                        value={baseQuery}
                                        onChange={(e) => setBaseQuery(e.target.value)}
                                      />
                                      {baseSearching && (
                                        <p className="mt-1 text-[10px] text-slate-500">Buscando…</p>
                                      )}
                                      <ul className="mt-1 max-h-36 space-y-1 overflow-y-auto">
                                        {baseHits.map((hit) => (
                                          <li key={`${hit.code}-${hit.score}`}>
                                            <button
                                              type="button"
                                              className="w-full rounded border border-white/5 bg-slate-950/80 px-2 py-1.5 text-left hover:border-brand-500/30 hover:bg-brand-500/5"
                                              onClick={() => replaceFromBase(si, ii, hit)}
                                            >
                                              <span className="font-mono text-xs text-brand-200">{hit.code}</span>
                                              <span className="ml-1 text-[10px] text-slate-500">{hit.unit}</span>
                                              <span className="ml-1 text-[10px] text-emerald-400">
                                                R$ {fmtBRL(hit.price_comd)}
                                              </span>
                                              <p className="line-clamp-1 text-[10px] text-slate-300">
                                                {hit.description}
                                              </p>
                                            </button>
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                  <label className="mt-2 block text-[10px] uppercase text-slate-500">
                                    Memória de cálculo
                                  </label>
                                  <textarea
                                    className="mt-0.5 h-24 w-full rounded border border-white/10 bg-slate-950 px-2 py-1.5 font-mono text-[11px] text-slate-200"
                                    value={it.memory ?? ""}
                                    onChange={(e) => updateItem(si, ii, { memory: e.target.value })}
                                  />
                                  <div className="mt-2 flex justify-end">
                                    <button
                                      type="button"
                                      className="text-[11px] text-rose-300 hover:text-rose-200"
                                      onClick={() => removeItem(si, ii)}
                                    >
                                      Remover composição
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                            {n === 0 && !pickerOpen && (
                              <p className="text-xs text-slate-500">
                                Use <strong>Buscar na base</strong> para adicionar composições.
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        </div>
      </div>

      <ActionDialog
        open={confirm.open}
        title={confirm.title}
        message={confirm.message}
        variant="confirm"
        confirmLabel="Confirmar"
        cancelLabel="Cancelar"
        destructive={confirm.title.includes("Excluir")}
        onCancel={() => setConfirm((c) => ({ ...c, open: false, onConfirm: undefined }))}
        onConfirm={confirm.onConfirm}
      />
    </>
  );
}
