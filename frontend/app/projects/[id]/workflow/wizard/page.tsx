"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import WorkspaceExpandButton, { WorkspaceCollapseStrip } from "@/components/WorkspaceExpandButton";
import { api } from "@/services/api";
import type {
  DeliveryPackageDetail,
  DeliveryPackageSummary,
  ProjectNormGaps,
  SheetTemplateItem,
} from "@/types/api";

const STEPS = [
  { id: 1, label: "Emissão" },
  { id: 2, label: "Arquivos" },
  { id: 3, label: "Template" },
  { id: 4, label: "Nomenclatura IA" },
  { id: 5, label: "Publicar GRD" },
];

export default function DeliveryWizardPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = String(params.id);

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [packages, setPackages] = useState<DeliveryPackageSummary[]>([]);
  const [detail, setDetail] = useState<DeliveryPackageDetail | null>(null);
  const [templates, setTemplates] = useState<SheetTemplateItem[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());

  const packageId = detail?.package.id ?? searchParams.get("package");

  const loadTemplates = useCallback(async () => {
    const res = await api.sheetTemplates();
    setTemplates(res.items);
  }, []);

  const loadPackages = useCallback(async () => {
    const res = await api.listDeliveryPackages(projectId);
    setPackages(res.items);
  }, [projectId]);

  const loadPackage = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getDeliveryPackage(projectId, id);
        setDetail(data);
        setSelectedFiles(new Set(data.items.filter((i) => i.selected).map((i) => i.project_file_id)));
        router.replace(`/projects/${projectId}/workflow/wizard?package=${id}`, { scroll: false });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erro ao carregar pacote");
      } finally {
        setLoading(false);
      }
    },
    [projectId, router],
  );

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        await Promise.all([loadTemplates(), loadPackages()]);
        const pid = searchParams.get("package");
        if (pid) {
          await loadPackage(pid);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erro ao iniciar wizard");
      } finally {
        setLoading(false);
      }
    })();
  }, [loadPackage, loadPackages, loadTemplates, searchParams]);

  const createNew = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await api.createDeliveryPackage(projectId);
      setDetail(data);
      setPackages((prev) => [data.package as DeliveryPackageSummary, ...prev]);
      setSelectedFiles(new Set());
      setStep(1);
      router.replace(`/projects/${projectId}/workflow/wizard?package=${data.package.id}`, { scroll: false });
      setNotice("Nova emissão criada — configure e selecione os arquivos.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar emissão");
    } finally {
      setBusy(false);
    }
  };

  const saveEmissao = async () => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const p = detail.package;
      setDetail(
        await api.updateDeliveryPackage(projectId, p.id, {
          titulo: p.titulo,
          codigo_emissao: p.codigo_emissao,
          formato_padrao: p.formato_padrao,
          orientacao_padrao: p.orientacao_padrao,
          template_id: p.template_id,
          observacoes: p.observacoes ?? undefined,
        }),
      );
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar emissão");
    } finally {
      setBusy(false);
    }
  };

  const saveSelection = async () => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      setDetail(
        await api.updateDeliverySelection(projectId, detail.package.id, Array.from(selectedFiles)),
      );
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar seleção");
    } finally {
      setBusy(false);
    }
  };

  const saveTemplate = async () => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const p = detail.package;
      setDetail(
        await api.updateDeliveryPackage(projectId, p.id, {
          formato_padrao: p.formato_padrao,
          orientacao_padrao: p.orientacao_padrao,
          template_id: p.template_id,
        }),
      );
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar template");
    } finally {
      setBusy(false);
    }
  };

  const runAnalysis = async () => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      setDetail(await api.analyzeDeliveryPackage(projectId, detail.package.id));
      setNotice("Análise concluída — revise nomenclaturas antes de publicar.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na análise IA");
    } finally {
      setBusy(false);
    }
  };

  const updateItemCode = async (itemId: string, codigo: string) => {
    if (!detail) return;
    try {
      setDetail(await api.updateDeliveryItem(projectId, detail.package.id, itemId, { codigo_aprovado: codigo }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar item");
    }
  };

  const publish = async () => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.publishDeliveryPackage(projectId, detail.package.id);
      setNotice(`Pacote ${result.package?.codigo_emissao} publicado — ${result.total_items} documento(s).`);
      await loadPackage(detail.package.id);
      setStep(5);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao publicar");
    } finally {
      setBusy(false);
    }
  };

  const filteredTemplates = useMemo(() => {
    if (!detail) return templates;
    return templates.filter(
      (t) =>
        t.formato === detail.package.formato_padrao &&
        t.orientacao === detail.package.orientacao_padrao,
    );
  }, [detail, templates]);

  if (loading && !detail) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <LoadingSpinner label="Carregando wizard de entrega..." size="lg" />
      </div>
    );
  }

  return (
    <>
      <WorkspaceCollapseStrip />
      <ShellHeader
        className="px-6"
        trailing={
          <Link
            href={`/projects/${projectId}/workflow`}
            className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-300 ring-1 ring-slate-700 hover:bg-slate-700"
          >
            Dashboard workflow
          </Link>
        }
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <WorkspaceExpandButton />
          <div className="min-w-0">
            <p className="text-xs text-slate-500">Workflow Projetos / Wizard de Entrega</p>
            <h1 className="truncate text-lg font-semibold text-white">Nova entrega ao cliente (GRD)</h1>
            <p className="mt-0.5 text-sm text-slate-400">
              Padrão escritório — seleção, nomenclatura, template A0–A4, pacote ZIP
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

      {detail?.norm_gaps?.has_any_gaps && (
        <NormGapsAlert
          gaps={detail.norm_gaps}
          projectId={projectId}
          packageId={detail.package.id}
        />
      )}

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-5xl">
          {!detail ? (
            <StartPanel packages={packages} busy={busy} onCreate={createNew} onOpen={loadPackage} projectId={projectId} />
          ) : (
            <>
              <Stepper current={step} status={detail.package.status} />
              <div className="mt-6 rounded-2xl bg-slate-900/60 p-6 ring-1 ring-slate-800">
                {step === 1 && (
                  <StepEmissao
                    detail={detail}
                    onChange={setDetail}
                    onNext={saveEmissao}
                    busy={busy}
                  />
                )}
                {step === 2 && (
                  <StepArquivos
                    detail={detail}
                    selected={selectedFiles}
                    onToggle={(id, on) => {
                      const next = new Set(selectedFiles);
                      if (on) next.add(id);
                      else next.delete(id);
                      setSelectedFiles(next);
                    }}
                    onBack={() => setStep(1)}
                    onNext={saveSelection}
                    busy={busy}
                  />
                )}
                {step === 3 && (
                  <StepTemplate
                    detail={detail}
                    templates={filteredTemplates}
                    allTemplates={templates}
                    onChange={setDetail}
                    onBack={() => setStep(2)}
                    onNext={saveTemplate}
                    busy={busy}
                  />
                )}
                {step === 4 && (
                  <StepNomenclatura
                    detail={detail}
                    onAnalyze={runAnalysis}
                    onUpdateCode={updateItemCode}
                    onBack={() => setStep(3)}
                    onNext={() => setStep(5)}
                    busy={busy}
                  />
                )}
                {step === 5 && (
                  <StepPublicar
                    detail={detail}
                    onBack={() => setStep(4)}
                    onPublish={publish}
                    busy={busy}
                    projectId={projectId}
                  />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

function NormGapsAlert({
  gaps,
  projectId,
  packageId,
}: {
  gaps: ProjectNormGaps;
  projectId: string;
  packageId: string;
}) {
  const critical = gaps.pending_items.filter((p) => p.critical);
  const isCritical = gaps.has_critical_gaps;

  return (
    <div
      className={`mx-6 mt-4 rounded-xl px-4 py-4 ring-1 ${
        isCritical
          ? "bg-amber-500/10 ring-amber-500/35"
          : "bg-slate-800/50 ring-slate-700"
      }`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`text-sm font-medium ${isCritical ? "text-amber-200" : "text-slate-200"}`}>
            Pendências normativas (NBR)
          </p>
          <p className="mt-1 text-sm text-slate-400">{gaps.summary_message}</p>
          <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto text-sm">
            {(critical.length > 0 ? critical : gaps.pending_items.slice(0, 8)).map((item) => (
              <li key={`${item.pack_id}-${item.nbr_code}`} className="flex flex-wrap gap-x-2 text-slate-300">
                <span className="font-mono text-cyan-300/90">NBR {item.nbr_code}</span>
                <span className="text-slate-500">·</span>
                <span className={item.status === "missing" ? "text-amber-300" : "text-violet-300"}>
                  {item.status === "missing" ? "Comprar PDF" : "Indexar"}
                </span>
                {item.critical && (
                  <span className="text-[10px] uppercase text-amber-400">crítica</span>
                )}
              </li>
            ))}
          </ul>
          {gaps.pending_total > 8 && (
            <p className="mt-2 text-xs text-slate-500">
              +{gaps.pending_total - 8} pendência(s) — exporte o CSV para lista completa.
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            href={gaps.settings_path ?? "/settings/norm-packs"}
            className="rounded-lg bg-cyan-500/15 px-3 py-2 text-xs font-medium text-cyan-300 ring-1 ring-cyan-500/30 hover:bg-cyan-500/25"
          >
            Pacotes NBR
          </Link>
          <button
            type="button"
            onClick={() => api.downloadDeliveryNormGapsCsv(projectId, packageId)}
            className="rounded-lg bg-slate-800 px-3 py-2 text-xs text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700"
          >
            Exportar CSV
          </button>
        </div>
      </div>
    </div>
  );
}

function StartPanel({
  packages,
  busy,
  onCreate,
  onOpen,
  projectId,
}: {
  packages: DeliveryPackageSummary[];
  busy: boolean;
  onCreate: () => void;
  onOpen: (id: string) => void;
  projectId: string;
}) {
  return (
    <div className="rounded-2xl bg-slate-900/60 p-6 ring-1 ring-slate-800">
      <h2 className="text-lg font-medium text-white">Emissões de entrega</h2>
      <p className="mt-2 text-sm text-slate-400">
        Como coordenador de projetos: cada emissão gera GRD, nomenclatura padronizada e ZIP para o cliente.
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={onCreate}
        className="mt-4 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
      >
        {busy ? "Criando..." : "+ Nova emissão"}
      </button>
      {packages.length > 0 && (
        <ul className="mt-6 space-y-2">
          {packages.map((p) => (
            <li key={p.id} className="flex items-center justify-between rounded-lg bg-slate-800/50 px-4 py-3">
              <div>
                <p className="text-sm text-white">{p.titulo}</p>
                <p className="text-xs text-slate-500">
                  {p.codigo_emissao} · {p.status}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onOpen(p.id)}
                className="text-sm text-cyan-400 hover:text-cyan-300"
              >
                Abrir
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-6 text-xs text-slate-500">
        Projeto{" "}
        <Link href={`/projects/${projectId}`} className="text-cyan-400 hover:underline">
          voltar ao workspace
        </Link>
      </p>
    </div>
  );
}

function Stepper({ current, status }: { current: number; status: string }) {
  return (
    <ol className="flex flex-wrap gap-2">
      {STEPS.map((s) => (
        <li
          key={s.id}
          className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ${
            s.id === current
              ? "bg-cyan-600/20 text-cyan-300 ring-cyan-500/40"
              : s.id < current
                ? "bg-slate-800 text-slate-400 ring-slate-700"
                : "bg-slate-900 text-slate-600 ring-slate-800"
          }`}
        >
          {s.id}. {s.label}
        </li>
      ))}
      <li className="ml-auto rounded-full bg-slate-800 px-3 py-1 text-xs uppercase text-slate-400 ring-1 ring-slate-700">
        {status}
      </li>
    </ol>
  );
}

function StepEmissao({
  detail,
  onChange,
  onNext,
  busy,
}: {
  detail: DeliveryPackageDetail;
  onChange: (d: DeliveryPackageDetail) => void;
  onNext: () => void;
  busy: boolean;
}) {
  const p = detail.package;
  return (
    <div>
      <h2 className="font-medium text-white">1. Dados da emissão</h2>
      <p className="mt-1 text-sm text-slate-400">
        Código de revisão da entrega (GRD) — incremento automático a partir da versão atual do projeto.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-slate-400">Título da entrega</span>
          <input
            className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-white ring-1 ring-slate-700"
            value={p.titulo}
            onChange={(e) =>
              onChange({ ...detail, package: { ...p, titulo: e.target.value } })
            }
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-400">Código emissão (REV)</span>
          <input
            className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-white ring-1 ring-slate-700"
            value={p.codigo_emissao}
            onChange={(e) =>
              onChange({ ...detail, package: { ...p, codigo_emissao: e.target.value } })
            }
          />
        </label>
      </div>
      <div className="mt-6 flex justify-end">
        <button
          type="button"
          disabled={busy}
          onClick={onNext}
          className="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          Próximo: selecionar arquivos
        </button>
      </div>
    </div>
  );
}

function StepArquivos({
  detail,
  selected,
  onToggle,
  onBack,
  onNext,
  busy,
}: {
  detail: DeliveryPackageDetail;
  selected: Set<string>;
  onToggle: (id: string, on: boolean) => void;
  onBack: () => void;
  onNext: () => void;
  busy: boolean;
}) {
  const files = detail.available_files;
  return (
    <div>
      <h2 className="font-medium text-white">2. Selecionar arquivos</h2>
      <p className="mt-1 text-sm text-slate-400">
        DWG, IFC, PDF pranchas e documentação complementar (MD, MC, pareceres). Você decide o que entra no pacote.
      </p>
      <ul className="mt-4 max-h-96 space-y-2 overflow-auto">
        {files.map((f) => (
          <li key={f.id} className="flex items-center gap-3 rounded-lg bg-slate-800/40 px-3 py-2">
            <input
              type="checkbox"
              checked={selected.has(f.id)}
              onChange={(e) => onToggle(f.id, e.target.checked)}
              className="size-4 rounded border-slate-600"
            />
            <span className="min-w-0 flex-1 truncate text-sm text-slate-200">{f.filename}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500">{selected.size} arquivo(s) selecionado(s)</p>
      <div className="mt-6 flex justify-between">
        <button type="button" onClick={onBack} className="text-sm text-slate-400 hover:text-white">
          Voltar
        </button>
        <button
          type="button"
          disabled={busy || selected.size === 0}
          onClick={onNext}
          className="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          Próximo: template de prancha
        </button>
      </div>
    </div>
  );
}

function StepTemplate({
  detail,
  templates,
  allTemplates,
  onChange,
  onBack,
  onNext,
  busy,
}: {
  detail: DeliveryPackageDetail;
  templates: SheetTemplateItem[];
  allTemplates: SheetTemplateItem[];
  onChange: (d: DeliveryPackageDetail) => void;
  onBack: () => void;
  onNext: () => void;
  busy: boolean;
}) {
  const p = detail.package;
  const formatos = [...new Set(allTemplates.map((t) => t.formato))];

  return (
    <div>
      <h2 className="font-medium text-white">3. Template de prancha e carimbo</h2>
      <p className="mt-1 text-sm text-slate-400">Formato físico da folha (A4 a A0) e orientação — padrão de grandes escritórios.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <label className="block text-sm">
          <span className="text-slate-400">Formato</span>
          <select
            className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-white ring-1 ring-slate-700"
            value={p.formato_padrao}
            onChange={(e) => {
              const formato = e.target.value;
              const match = allTemplates.find(
                (t) => t.formato === formato && t.orientacao === p.orientacao_padrao,
              );
              onChange({
                ...detail,
                package: {
                  ...p,
                  formato_padrao: formato,
                  template_id: match?.id ?? p.template_id,
                },
              });
            }}
          >
            {formatos.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="text-slate-400">Orientação</span>
          <select
            className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-white ring-1 ring-slate-700"
            value={p.orientacao_padrao}
            onChange={(e) => {
              const orientacao = e.target.value;
              const match = allTemplates.find(
                (t) => t.formato === p.formato_padrao && t.orientacao === orientacao,
              );
              onChange({
                ...detail,
                package: {
                  ...p,
                  orientacao_padrao: orientacao,
                  template_id: match?.id ?? p.template_id,
                },
              });
            }}
          >
            <option value="paisagem">Paisagem</option>
            <option value="retrato">Retrato</option>
          </select>
        </label>
        <label className="block text-sm">
          <span className="text-slate-400">Template</span>
          <select
            className="mt-1 w-full rounded-lg bg-slate-800 px-3 py-2 text-white ring-1 ring-slate-700"
            value={p.template_id ?? ""}
            onChange={(e) =>
              onChange({ ...detail, package: { ...p, template_id: e.target.value || null } })
            }
          >
            <option value="">Padrão do sistema</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.nome}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="mt-6 flex justify-between">
        <button type="button" onClick={onBack} className="text-sm text-slate-400 hover:text-white">
          Voltar
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onNext}
          className="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          Próximo: nomenclatura IA
        </button>
      </div>
    </div>
  );
}

function StepNomenclatura({
  detail,
  onAnalyze,
  onUpdateCode,
  onBack,
  onNext,
  busy,
}: {
  detail: DeliveryPackageDetail;
  onAnalyze: () => void;
  onUpdateCode: (itemId: string, code: string) => void;
  onBack: () => void;
  onNext: () => void;
  busy: boolean;
}) {
  const selectedItems = detail.items.filter((i) => i.selected);
  const analyzed = selectedItems.some((i) => i.codigo_sugerido);

  return (
    <div>
      <h2 className="font-medium text-white">4. Nomenclatura e classificação (IA)</h2>
      <p className="mt-1 text-sm text-slate-400">
        Padrão <code className="text-cyan-300">DISC-FLnn-TIPO-DESC-REV</code> — ex.: ARQ-FL01-PLANTA-TERREO-R02
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={onAnalyze}
        className="mt-4 rounded-lg bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-500 disabled:opacity-50"
      >
        {busy ? "Analisando..." : analyzed ? "Reanalisar arquivos" : "Executar análise IA"}
      </button>
      {selectedItems.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          {selectedItems.some((i) => i.analysis?.normative_rag?.rag_available) && (
            <p className="mb-3 text-xs text-violet-300">
              NBRs consultadas na base:{" "}
              {[
                ...new Set(
                  selectedItems.flatMap(
                    (i) => (i.analysis?.normative_rag as { nbrs_cited?: string[] })?.nbrs_cited ?? [],
                  ),
                ),
              ].join(", ") || "—"}
            </p>
          )}
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="text-xs uppercase text-slate-500">
                <th className="pb-2 pr-2">Arquivo</th>
                <th className="pb-2 pr-2">Papel</th>
                <th className="pb-2 pr-2">Pasta</th>
                <th className="pb-2">Código aprovado</th>
              </tr>
            </thead>
            <tbody>
              {selectedItems.map((item) => (
                <tr key={item.id} className="border-t border-slate-800">
                  <td className="py-2 pr-2 text-slate-300">{item.filename}</td>
                  <td className="py-2 pr-2">
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs uppercase">{item.role}</span>
                  </td>
                  <td className="py-2 pr-2 text-xs text-slate-500">{item.pasta_destino ?? "—"}</td>
                  <td className="py-2">
                    <input
                      className="w-full rounded bg-slate-800 px-2 py-1 text-xs text-white ring-1 ring-slate-700"
                      value={item.codigo_aprovado ?? item.codigo_sugerido ?? ""}
                      onChange={(e) => onUpdateCode(item.id, e.target.value)}
                      placeholder={item.codigo_sugerido ?? "—"}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-6 flex justify-between">
        <button type="button" onClick={onBack} className="text-sm text-slate-400 hover:text-white">
          Voltar
        </button>
        <button
          type="button"
          disabled={!analyzed}
          onClick={onNext}
          className="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          Revisar pacote GRD
        </button>
      </div>
    </div>
  );
}

function StepPublicar({
  detail,
  onBack,
  onPublish,
  busy,
  projectId,
}: {
  detail: DeliveryPackageDetail;
  onBack: () => void;
  onPublish: () => void;
  busy: boolean;
  projectId: string;
}) {
  const tree = detail.structure_preview;
  const published = detail.package.status === "published";

  return (
    <div>
      <h2 className="font-medium text-white">5. Publicar pacote de entrega</h2>
      <p className="mt-1 text-sm text-slate-400">
        Estrutura GRD — pranchas por disciplina, memoriais, cálculos e correspondências em ZIP + PDF guia.
      </p>
      <div className="mt-4 rounded-lg bg-slate-800/40 p-4 font-mono text-xs text-slate-300">
        {Object.keys(tree).length === 0 ? (
          <p className="text-slate-500">Execute a anália na etapa anterior.</p>
        ) : (
          Object.entries(tree).map(([folder, files]) => (
            <div key={folder} className="mb-3">
              <p className="text-cyan-400">{folder}/</p>
              {files.map((f) => (
                <p key={f} className="ml-4 text-slate-400">
                  {f}
                </p>
              ))}
            </div>
          ))
        )}
      </div>
      {published ? (
        <p className="mt-4 text-sm text-emerald-400">Emissão publicada. Consulte entregas no dashboard workflow.</p>
      ) : (
        <button
          type="button"
          disabled={busy || Object.keys(tree).length === 0}
          onClick={onPublish}
          className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {busy ? "Publicando..." : "Gerar ZIP + GRD"}
        </button>
      )}
      <div className="mt-6 flex justify-between">
        <button type="button" onClick={onBack} className="text-sm text-slate-400 hover:text-white">
          Voltar
        </button>
        <Link href={`/projects/${projectId}/workflow`} className="text-sm text-cyan-400 hover:text-cyan-300">
          Ir ao dashboard
        </Link>
      </div>
    </div>
  );
}
