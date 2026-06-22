"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "@/services/api";
import type {
  OpenCompositionDetail,
  PriceBankInventory,
  PriceBankInventoryGroup,
  PriceBankReference,
  PriceBankStats,
  PriceSyncResult,
  PriceSyncSourceInfo,
  WebIngestProgress,
} from "@/types/api";
import { cn } from "@/lib/utils";
import ActionDialog from "@/components/ActionDialog";
import {
  openExternalUrl,
  sinapiDefaultPeriod,
  sinapiNationalDownloadsUrl,
} from "@/lib/sinapi-links";

import { BRAZIL_UFS, referenceLabelFromKey } from "@/lib/brazil-ufs";

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);
const SYNC_YEARS = Array.from({ length: 4 }, (_, i) => new Date().getFullYear() - i);
const NEW_SOURCE_OPTION = "__new__";

function referenceLabel(reference: string, refs: PriceBankReference[] = []): string {
  const found = refs.find((r) => r.reference === reference);
  if (found?.label) return found.label;
  return referenceLabelFromKey(reference);
}

function sourceKey(ref: PriceBankReference): string {
  return (ref.source || "sinapi").toLowerCase();
}

function acceptForSource(source: string): string {
  if (source === "ppd_seminf") return ".xlsm,.xlsx,.xls";
  if (source === "sinapi") return ".zip,.xlsx,.xls";
  return ".zip,.xlsx,.xls,.csv";
}

function ExternalLink({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      onClick={(e) => {
        e.preventDefault();
        openExternalUrl(href);
      }}
    >
      {children}
    </a>
  );
}

function PriceImportProgressBar({ progress }: { progress: WebIngestProgress | null }) {
  if (!progress) return null;
  const pct = Math.min(100, Math.max(0, progress.percent ?? 0));
  return (
    <div className="rounded-xl bg-slate-900/80 p-4 ring-1 ring-cyan-500/30">
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-cyan-200">{progress.message || "Importando…"}</span>
        <span className="tabular-nums text-cyan-300">{pct}%</span>
      </div>
      <div
        className="h-2.5 overflow-hidden rounded-full bg-slate-800"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-[width] duration-300 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      {progress.phase && (
        <p className="mt-2 text-xs uppercase tracking-wide text-slate-500">Fase: {progress.phase}</p>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: number | string;
  hint?: string;
  accent?: "emerald" | "cyan" | "amber";
}) {
  const colors = {
    emerald: "text-emerald-300 ring-emerald-500/30 bg-emerald-500/10",
    cyan: "text-cyan-300 ring-cyan-500/30 bg-cyan-500/10",
    amber: "text-amber-300 ring-amber-500/30 bg-amber-500/10",
  };
  return (
    <div className={cn("rounded-xl p-4 ring-1", colors[accent ?? "emerald"])}>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function defaultDownloadUrl(source: string, year: number, month: number): string {
  if (source === "sinapi") return sinapiNationalDownloadsUrl();
  if (source === "ppd_seminf") return "";
  return "";
}

function SourceHint({
  source,
  year,
  month,
  downloadUrl,
}: {
  source: string;
  year: number;
  month: number;
  downloadUrl: string;
}) {
  if (source === NEW_SOURCE_OPTION) return null;
  if (downloadUrl.trim()) {
    return (
      <p className="text-xs text-slate-500">
        Página de download configurada — use <strong className="text-slate-400">Abrir página</strong> ou importe o
        arquivo localmente.
      </p>
    );
  }
  if (source === "sinapi") {
    return (
      <p className="text-xs text-slate-500">
        Portal nacional (categoria_888):{" "}
        <ExternalLink href={sinapiNationalDownloadsUrl()} className="text-cyan-400 underline">
          downloads.aspx — SINAPI mensal
        </ExternalLink>
        . O <strong className="text-slate-400">download automático</strong> consulta essa página
        (API SharePoint da Caixa) e baixa o ZIP XLSX do período — inclusive retificações
        (ex. FEV/2026 → <code className="text-slate-400">_Retificacao01</code>).
      </p>
    );
  }
  if (source === "ppd_seminf") {
    return (
      <p className="text-xs text-slate-500">
        Planilha MC_OR da SEMINF/SEINFRA-AM (.xlsm). Composições fechadas com preços regionais (UF AM).
      </p>
    );
  }
  return (
    <p className="text-xs text-slate-500">
      Informe o link da página de download ao lado do período ou exporte CSV/XLSX/ZIP e use{" "}
      <strong className="text-slate-400">Importar</strong>.
    </p>
  );
}

export default function SettingsPriceBasesPage() {
  const defaultPeriod = sinapiDefaultPeriod();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [sources, setSources] = useState<PriceSyncSourceInfo[]>([]);
  const [inventory, setInventory] = useState<PriceBankInventory | null>(null);
  const [bank, setBank] = useState<PriceBankStats | null>(null);
  const [importSource, setImportSource] = useState("sinapi");
  const [syncing, setSyncing] = useState<string | null>(null);
  const [importProgress, setImportProgress] = useState<WebIngestProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [syncYear, setSyncYear] = useState(defaultPeriod.year);
  const [syncMonth, setSyncMonth] = useState(defaultPeriod.month);
  const [viewReference, setViewReference] = useState("");
  const [previewSource, setPreviewSource] = useState("sinapi");
  const [previewUf, setPreviewUf] = useState("SP");
  const [previewCode, setPreviewCode] = useState("");
  const [preview, setPreview] = useState<OpenCompositionDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewPriceMode, setPreviewPriceMode] = useState<"comd" | "semd">("comd");
  const [deleteRefConfirm, setDeleteRefConfirm] = useState<string | null>(null);
  const [deletingRef, setDeletingRef] = useState(false);
  const [purgingFaiss, setPurgingFaiss] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [savingUrl, setSavingUrl] = useState(false);
  const [showNewSourceForm, setShowNewSourceForm] = useState(false);
  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceLabel, setNewSourceLabel] = useState("");
  const [creatingSource, setCreatingSource] = useState(false);

  const references: PriceBankReference[] = bank?.references ?? inventory?.groups.flatMap((g) =>
    g.periods.map((p) => ({
      reference: p.reference,
      label: p.label,
      source: g.source,
      synced_at: p.synced_at,
      default_uf: p.default_uf,
      active: p.active,
      counts: p.counts,
      metadata: p.metadata,
    }))
  ) ?? [];

  const importSourceInfo = sources.find((s) => s.name === importSource);
  const canAutoDownload = importSourceInfo?.auto_download ?? false;
  const isCustomSource = importSourceInfo?.custom ?? false;

  const effectiveDownloadUrl = useMemo(() => {
    const saved = downloadUrl.trim();
    if (saved) return saved;
    return defaultDownloadUrl(importSource, syncYear, syncMonth);
  }, [downloadUrl, importSource, syncYear, syncMonth]);

  useEffect(() => {
    if (importSource === NEW_SOURCE_OPTION) return;
    const info = sources.find((s) => s.name === importSource);
    setDownloadUrl(info?.download_url ?? "");
  }, [importSource, sources]);

  const previewSources = useMemo(() => {
    const fromInventory = (inventory?.groups ?? [])
      .filter((g) => g.periods.length > 0)
      .map((g) => ({ name: g.source, label: g.label }));
    if (fromInventory.length > 0) return fromInventory;
    return sources.map((s) => ({ name: s.name, label: s.label }));
  }, [inventory, sources]);

  const previewReferences = useMemo(
    () => references.filter((r) => sourceKey(r) === previewSource),
    [references, previewSource]
  );

  const refresh = useCallback(async (reference?: string) => {
    const ref = reference ?? (viewReference || undefined);
    const [srcRes, invRes, bankRes] = await Promise.all([
      api.pricingSyncSources(),
      api.pricingSyncBankInventory(),
      api.pricingSyncBank(ref),
    ]);
    setSources(srcRes.sources);
    setInventory(invRes);
    setBank(bankRes);

    const allRefs = bankRes.references ?? [];
    const firstRef = ref || allRefs[0]?.reference || "";
    if (!viewReference && firstRef) {
      setViewReference(firstRef);
      const src = allRefs.find((r) => r.reference === firstRef);
      if (src?.source) setPreviewSource(src.source.toLowerCase());
    }
  }, [viewReference]);

  useEffect(() => {
    refresh().catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar"));
  }, [refresh]);

  useEffect(() => {
    if (previewReferences.length === 0) return;
    if (!previewReferences.some((r) => r.reference === viewReference)) {
      setViewReference(previewReferences[0].reference);
    }
  }, [previewSource, previewReferences, viewReference]);

  const formatBrl = (value: number) =>
    value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

  const previewTotalSemd = (comp: OpenCompositionDetail) =>
    comp.total_price_sem ??
    comp.items.reduce((sum, item) => sum + (item.partial_cost_sem ?? item.partial_cost), 0);

  const metaCount = (meta: Record<string, unknown> | undefined, key: string) => {
    const v = meta?.[key];
    return typeof v === "number" ? v : undefined;
  };

  const formatSyncSuccess = (name: string, result: PriceSyncResult) => {
    const meta = result.download?.metadata;
    const closed = metaCount(meta, "compositions_closed") ?? result.item_count ?? 0;
    const open = metaCount(meta, "compositions_open");
    const insumos = metaCount(meta, "insumos");
    return `${name.toUpperCase()} importado — fechadas: ${closed}, abertas: ${open ?? "—"}, insumos: ${insumos ?? "—"}`;
  };

  const handleSync = async (name: string) => {
    setSyncing(name);
    setImportProgress({ phase: "start", percent: 0, current: 0, total: 0, message: "Iniciando…" });
    setError(null);
    setSuccess(null);
    try {
      const result = await api.pricingSyncSourceWithProgress(
        name,
        {
          year: syncYear,
          month: syncMonth,
          index_faiss: false,
          reload_providers: false,
          set_active: false,
        },
        (p) => setImportProgress(p)
      );
      const refKey =
        (typeof result.download?.metadata?.reference === "string"
          ? result.download.metadata.reference
          : null) ?? `BR-${syncYear}-${String(syncMonth).padStart(2, "0")}`;
      setViewReference(refKey);
      setPreviewSource(name);
      setSuccess(formatSyncSuccess(name, result));
      await refresh(refKey);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha na sincronização");
    } finally {
      setSyncing(null);
      setImportProgress(null);
    }
  };

  const handleUpload = async (name: string, file: File) => {
    setSyncing(name);
    setImportProgress({ phase: "start", percent: 0, current: 0, total: 0, message: `Enviando ${file.name}…` });
    setError(null);
    setSuccess(null);
    try {
      const result = await api.pricingSyncUploadWithProgress(
        name,
        file,
        {
          year: syncYear,
          month: syncMonth,
          set_active: false,
          index_faiss: false,
          reload_providers: false,
        },
        (p) => setImportProgress(p)
      );
      const refKey =
        (typeof result.download?.metadata?.reference === "string"
          ? result.download.metadata.reference
          : null) ?? viewReference;
      if (refKey) {
        setViewReference(refKey);
        setPreviewSource(name);
      }
      setSuccess(formatSyncSuccess(file.name, result));
      await refresh(refKey || undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha no upload");
    } finally {
      setSyncing(null);
      setImportProgress(null);
    }
  };

  const loadPreview = async (opts?: { uf?: string; reference?: string }) => {
    if (!previewCode.trim()) return;
    const queryUf = opts?.uf ?? previewUf;
    const queryRef = opts?.reference ?? (viewReference ? viewReference : undefined);
    setPreviewLoading(true);
    try {
      const comp = await api.pricingSyncOpenComposition(previewCode.trim(), {
        uf: queryUf,
        reference: queryRef,
      });
      setPreview(comp);
    } catch (e) {
      setPreview(null);
      setError(e instanceof Error ? e.message : "Composição não encontrada");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handlePreviewUfChange = (nextUf: string) => {
    setPreviewUf(nextUf);
    if (preview && previewCode.trim()) {
      void loadPreview({ uf: nextUf });
    }
  };

  const handlePreviewSourceChange = (source: string) => {
    setPreviewSource(source);
    const refs = references.filter((r) => sourceKey(r) === source);
    if (refs[0]) {
      void handleViewReferenceChange(refs[0].reference);
    }
  };

  const handleViewReferenceChange = async (reference: string) => {
    setViewReference(reference);
    try {
      const bankRes = await api.pricingSyncBank(reference);
      setBank(bankRes);
      if (preview && previewCode.trim()) {
        await loadPreview({ reference });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar referência");
    }
  };

  const handleDeleteReference = async (reference: string) => {
    setDeletingRef(true);
    setError(null);
    try {
      const result = await api.pricingSyncDeleteReference(reference);
      setDeleteRefConfirm(null);
      setPreview(null);
      setViewReference("");
      const faissRemoved = result.faiss_purge?.chunks_removed ?? 0;
      setSuccess(
        `Referência ${referenceLabel(reference, references)} excluída do banco.${
          faissRemoved > 0 ? ` ${faissRemoved.toLocaleString("pt-BR")} chunks RAG legados removidos.` : ""
        }`
      );
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao excluir referência");
    } finally {
      setDeletingRef(false);
    }
  };

  const handleSaveDownloadUrl = async () => {
    if (importSource === NEW_SOURCE_OPTION) return;
    setSavingUrl(true);
    setError(null);
    try {
      await api.pricingSyncUpdateSourceConfig(importSource, { download_url: downloadUrl });
      setSuccess("Link de download salvo.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar link");
    } finally {
      setSavingUrl(false);
    }
  };

  const handleCreateSource = async () => {
    if (!newSourceName.trim() || !newSourceLabel.trim()) {
      setError("Informe identificador e nome da nova base.");
      return;
    }
    setCreatingSource(true);
    setError(null);
    try {
      const res = await api.pricingSyncCreateSource({
        name: newSourceName.trim(),
        label: newSourceLabel.trim(),
        download_url: downloadUrl.trim(),
      });
      const created = res.source.name;
      setShowNewSourceForm(false);
      setNewSourceName("");
      setNewSourceLabel("");
      setImportSource(created);
      setPreviewSource(created);
      setSuccess(`Tipo de base "${res.source.label}" criado.`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao criar tipo de base");
    } finally {
      setCreatingSource(false);
    }
  };

  const handleDeleteCustomSource = async () => {
    if (!isCustomSource) return;
    setError(null);
    try {
      await api.pricingSyncDeleteSource(importSource);
      setImportSource("sinapi");
      setSuccess("Tipo de base removido.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao remover tipo de base");
    }
  };

  const handlePurgeSinapiFaiss = async () => {
    setPurgingFaiss(true);
    setError(null);
    try {
      const result = await api.pricingPurgeSinapiFaiss();
      setSuccess(
        `Índice RAG SINAPI limpo — ${result.chunks_removed.toLocaleString("pt-BR")} chunks removidos (${result.remaining.toLocaleString("pt-BR")} restantes).`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao limpar índice RAG");
    } finally {
      setPurgingFaiss(false);
    }
  };

  const totals = inventory?.totals;
  const hasData = (inventory?.period_count ?? 0) > 0;

  const renderInventoryGroup = (group: PriceBankInventoryGroup) => {
    if (group.periods.length === 0) return null;
    return (
      <div key={group.source} className="space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{group.label}</h4>
        <div className="overflow-x-auto rounded-lg ring-1 ring-slate-800">
          <table className="w-full text-left text-xs text-slate-400">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-500">
                <th className="px-3 py-2">Período</th>
                <th className="px-3 py-2 text-right">Fechadas</th>
                <th className="px-3 py-2 text-right">Abertas</th>
                <th className="px-3 py-2 text-right">Itens analít.</th>
                <th className="px-3 py-2 text-right">Insumos</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {group.periods.map((p) => (
                <tr
                  key={p.reference}
                  className={cn(
                    "border-b border-slate-800/80",
                    p.reference === viewReference && "bg-cyan-500/5"
                  )}
                >
                  <td className="px-3 py-2 font-medium text-slate-200">
                    {p.label}
                    {p.active && (
                      <span className="ml-2 rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] text-emerald-300">
                        ativo
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(p.counts?.compositions_closed ?? 0).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(p.counts?.compositions_open ?? 0).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(p.counts?.open_items_total ?? 0).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {(p.counts?.insumos ?? 0).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      disabled={!!syncing || deletingRef}
                      onClick={() => setDeleteRefConfirm(p.reference)}
                      className="text-red-400/80 hover:text-red-300 disabled:opacity-50"
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Bases de preços públicas</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-400">
          Importe e gerencie SINAPI, PPD/SEMINF, SICRO, ORSE e outras bases em um único fluxo.
          Composições fechadas e abertas (CPUs) alimentam o orçamento automático.
        </p>
      </div>

      {importProgress && syncing && <PriceImportProgressBar progress={importProgress} />}

      {error && (
        <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">{error}</div>
      )}
      {success && (
        <div className="rounded-xl bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300 ring-1 ring-emerald-500/30">
          {success}
        </div>
      )}

      <section className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Totais no banco</h3>
        {!hasData ? (
          <p className="mt-2 text-sm text-slate-500">Nenhuma base importada. Use o painel abaixo para começar.</p>
        ) : (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Composições fechadas"
              value={(totals?.compositions_closed ?? 0).toLocaleString("pt-BR")}
              hint={`${inventory?.period_count ?? 0} período(s) · ${inventory?.source_count ?? 0} fonte(s)`}
              accent="emerald"
            />
            <StatCard
              label="Composições abertas"
              value={(totals?.compositions_open ?? 0).toLocaleString("pt-BR")}
              hint="Analíticas — estrutura CPU"
              accent="cyan"
            />
            <StatCard
              label="Itens analíticos"
              value={(totals?.open_items_total ?? 0).toLocaleString("pt-BR")}
              hint="Insumos + MO + equip. por CPU"
              accent="cyan"
            />
            <StatCard
              label="Insumos"
              value={(totals?.insumos ?? 0).toLocaleString("pt-BR")}
              hint="Catálogo ISD/ICD"
              accent="amber"
            />
          </div>
        )}
      </section>

      <section className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Importar base de preços</h3>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-400">
            Tipo de base
            <select
              value={showNewSourceForm ? NEW_SOURCE_OPTION : importSource}
              onChange={(e) => {
                const v = e.target.value;
                if (v === NEW_SOURCE_OPTION) {
                  setShowNewSourceForm(true);
                  return;
                }
                setShowNewSourceForm(false);
                setImportSource(v);
              }}
              disabled={!!syncing || creatingSource}
              className="mt-1 block min-w-[200px] rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 disabled:opacity-50"
            >
              {sources.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.label}
                  {s.custom ? " (custom)" : ""}
                </option>
              ))}
              <option value={NEW_SOURCE_OPTION}>+ Adicionar novo tipo…</option>
            </select>
          </label>
          <label className="text-sm text-slate-400">
            Mês
            <select
              value={syncMonth}
              onChange={(e) => setSyncMonth(Number(e.target.value))}
              disabled={!!syncing || showNewSourceForm}
              className="mt-1 block rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 disabled:opacity-50"
            >
              {MONTHS.map((m) => (
                <option key={m} value={m}>
                  {String(m).padStart(2, "0")}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-slate-400">
            Ano
            <select
              value={syncYear}
              onChange={(e) => setSyncYear(Number(e.target.value))}
              disabled={!!syncing || showNewSourceForm}
              className="mt-1 block rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 disabled:opacity-50"
            >
              {SYNC_YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-[min(100%,280px)] flex-1 text-sm text-slate-400">
            Link da página de download
            <input
              type="url"
              value={downloadUrl}
              onChange={(e) => setDownloadUrl(e.target.value)}
              onBlur={() => {
                if (!showNewSourceForm && importSource !== NEW_SOURCE_OPTION) {
                  void handleSaveDownloadUrl();
                }
              }}
              disabled={!!syncing || savingUrl}
              placeholder={
                importSource === "sinapi"
                  ? sinapiNationalDownloadsUrl()
                  : "https://…"
              }
              className="mt-1 block w-full rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 placeholder:text-slate-600 disabled:opacity-50"
            />
          </label>
        </div>

        {showNewSourceForm && (
          <div className="mt-4 rounded-lg bg-slate-900/60 p-4 ring-1 ring-cyan-500/20">
            <p className="text-sm font-medium text-cyan-200">Novo tipo de base</p>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <label className="text-sm text-slate-400">
                Identificador
                <input
                  type="text"
                  value={newSourceName}
                  onChange={(e) => setNewSourceName(e.target.value)}
                  placeholder="ex.: pd_municipal"
                  disabled={creatingSource}
                  className="mt-1 block w-40 rounded-lg border-0 bg-slate-800 px-3 py-2 font-mono text-sm text-white ring-1 ring-slate-700 disabled:opacity-50"
                />
              </label>
              <label className="text-sm text-slate-400">
                Nome exibido
                <input
                  type="text"
                  value={newSourceLabel}
                  onChange={(e) => setNewSourceLabel(e.target.value)}
                  placeholder="ex.: PD Municipal XYZ"
                  disabled={creatingSource}
                  className="mt-1 block min-w-[200px] rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 disabled:opacity-50"
                />
              </label>
              <button
                type="button"
                disabled={creatingSource}
                onClick={() => void handleCreateSource()}
                className="rounded-lg bg-cyan-700/80 px-4 py-2 text-sm text-white hover:bg-cyan-600 disabled:opacity-50"
              >
                {creatingSource ? "Criando…" : "Criar tipo"}
              </button>
              <button
                type="button"
                disabled={creatingSource}
                onClick={() => {
                  setShowNewSourceForm(false);
                  setNewSourceName("");
                  setNewSourceLabel("");
                }}
                className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-300 ring-1 ring-slate-700 hover:bg-slate-700 disabled:opacity-50"
              >
                Cancelar
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Identificador: letras minúsculas, números e _ (sem espaços). O link acima será salvo junto com o novo
              tipo.
            </p>
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {canAutoDownload && !showNewSourceForm && (
            <button
              type="button"
              disabled={!!syncing}
              onClick={() => void handleSync(importSource)}
              className="rounded-lg bg-emerald-600/80 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {syncing === importSource ? "Baixando…" : "Download automático"}
            </button>
          )}
          {effectiveDownloadUrl && !showNewSourceForm && (
            <ExternalLink
              href={effectiveDownloadUrl}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-cyan-400 ring-1 ring-slate-700 hover:bg-slate-700"
            >
              Abrir página de download
            </ExternalLink>
          )}
          {!showNewSourceForm && (
            <button
              type="button"
              disabled={!!syncing}
              onClick={() => fileInputRef.current?.click()}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700 disabled:opacity-50"
            >
              {syncing === importSource ? "Importando…" : "Importar arquivo local"}
            </button>
          )}
          {isCustomSource && !showNewSourceForm && (
            <button
              type="button"
              disabled={!!syncing}
              onClick={() => void handleDeleteCustomSource()}
              className="rounded-lg bg-red-900/50 px-4 py-2 text-sm text-red-300 ring-1 ring-red-800 hover:bg-red-900 disabled:opacity-50"
            >
              Remover tipo customizado
            </button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept={acceptForSource(importSource)}
            className="hidden"
            disabled={!!syncing}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleUpload(importSource, f);
              e.target.value = "";
            }}
          />
        </div>

        <div className="mt-3">
          <SourceHint
            source={showNewSourceForm ? NEW_SOURCE_OPTION : importSource}
            year={syncYear}
            month={syncMonth}
            downloadUrl={downloadUrl}
          />
        </div>
      </section>

      {hasData && (
        <section className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
          <h3 className="text-sm font-semibold text-slate-200">Períodos importados</h3>
          <p className="mt-1 text-xs text-slate-500">
            Resumo por fonte e período. Clique em excluir para remover e reimportar.
          </p>
          <div className="mt-4 space-y-6">
            {(inventory?.groups ?? []).map(renderInventoryGroup)}
          </div>
        </section>
      )}

      <section className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Manutenção — índice RAG legado</h3>
        <p className="mt-1 text-xs text-slate-500">
          Importações antigas indexavam SINAPI no FAISS de conhecimento. O orçamento usa price_bank — esses chunks
          não são necessários.
        </p>
        <button
          type="button"
          disabled={!!syncing || deletingRef || purgingFaiss}
          onClick={() => void handlePurgeSinapiFaiss()}
          className="mt-3 rounded-lg bg-amber-700/80 px-3 py-2 text-sm text-white hover:bg-amber-600 disabled:opacity-50"
        >
          {purgingFaiss ? "Limpando…" : "Limpar índice RAG SINAPI"}
        </button>
      </section>

      <ActionDialog
        open={!!deleteRefConfirm}
        title="Excluir referência?"
        message={
          deleteRefConfirm
            ? `Remover ${referenceLabel(deleteRefConfirm, references)} do banco de preços?\n\nApaga composições e insumos deste período.`
            : ""
        }
        variant="confirm"
        destructive
        confirmLabel={deletingRef ? "Excluindo…" : "Excluir"}
        onConfirm={
          deletingRef || !deleteRefConfirm
            ? undefined
            : () => void handleDeleteReference(deleteRefConfirm)
        }
        onCancel={() => !deletingRef && setDeleteRefConfirm(null)}
      />

      <section className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Prévia — composição aberta (CPU)</h3>
        <p className="mt-1 text-xs text-slate-500">
          Consulte CPUs por código. Escolha tipo de base, período e UF.
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <input
            type="text"
            value={previewCode}
            onChange={(e) => setPreviewCode(e.target.value)}
            placeholder="Ex: 95995"
            className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
          />
          {previewSources.length > 0 && (
            <label className="text-sm text-slate-400">
              Tipo de base
              <select
                value={previewSource}
                onChange={(e) => handlePreviewSourceChange(e.target.value)}
                disabled={previewLoading}
                className="ml-2 rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 disabled:opacity-50"
              >
                {previewSources.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {previewReferences.length > 0 && (
            <label className="text-sm text-slate-400">
              Período
              <select
                value={viewReference}
                onChange={(e) => void handleViewReferenceChange(e.target.value)}
                disabled={previewLoading}
                className="ml-2 rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 disabled:opacity-50"
              >
                {previewReferences.map((r) => (
                  <option key={r.reference} value={r.reference}>
                    {r.label ?? referenceLabel(r.reference, references)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="text-sm text-slate-400">
            UF
            <select
              value={previewUf}
              onChange={(e) => handlePreviewUfChange(e.target.value)}
              disabled={previewLoading}
              className="ml-2 rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 disabled:opacity-50"
            >
              {BRAZIL_UFS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => void loadPreview()}
            disabled={previewLoading || !hasData}
            className="rounded-lg bg-cyan-700/80 px-4 py-2 text-sm text-white hover:bg-cyan-600 disabled:opacity-50"
          >
            {previewLoading ? "Carregando…" : "Consultar"}
          </button>
          {preview && (
            <label className="text-sm text-slate-400">
              Preços na tabela
              <select
                value={previewPriceMode}
                onChange={(e) => setPreviewPriceMode(e.target.value as "comd" | "semd")}
                className="ml-2 rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
              >
                <option value="comd">Com desoneração (ComD)</option>
                <option value="semd">Sem desoneração (SemD)</option>
              </select>
            </label>
          )}
        </div>
        {preview && (
          <div className="mt-4 overflow-x-auto">
            <p className="mb-2 text-sm text-slate-300">
              <strong>{preview.code}</strong> — {preview.description} ({preview.unit})
            </p>
            <div className="mb-3 flex flex-wrap gap-4 text-sm">
              <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-emerald-200 ring-1 ring-emerald-500/30">
                ComD (CCD): <strong className="tabular-nums">{formatBrl(preview.total_price)}</strong>
              </span>
              <span className="rounded-lg bg-cyan-500/10 px-3 py-1.5 text-cyan-200 ring-1 ring-cyan-500/30">
                SemD (CSD):{" "}
                <strong className="tabular-nums">{formatBrl(previewTotalSemd(preview))}</strong>
              </span>
              {(preview.price_uf || previewUf) && (
                <span className="self-center text-xs text-slate-500">
                  UF {preview.price_uf ?? previewUf}
                  {viewReference ? ` · ${referenceLabel(viewReference, references)}` : ""}
                </span>
              )}
            </div>
            {preview.analytical_total_com != null &&
              Math.abs(preview.analytical_total_com - preview.total_price) > 0.05 && (
                <p className="mb-2 text-xs text-slate-500">
                  CPU analítica (soma parciais ComD): {formatBrl(preview.analytical_total_com)}
                </p>
              )}
            {preview.period_variation && preview.period_variation.warnings.length > 0 && (
              <div className="mb-4 space-y-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3">
                <p className="text-sm font-medium text-amber-200">
                  Variação em relação a {preview.period_variation.previous_label ?? "mês anterior"}
                  {preview.period_variation.threshold_pct
                    ? ` (limiar ±${preview.period_variation.threshold_pct}%)`
                    : ""}
                </p>
                <ul className="space-y-1.5 text-xs text-amber-100/90">
                  {preview.period_variation.warnings.map((w, idx) => (
                    <li key={`${w.kind}-${w.code ?? ""}-${w.metric}-${idx}`} className="flex gap-2">
                      <span className="shrink-0 font-semibold tabular-nums text-amber-300">
                        {w.change_pct > 0 ? "+" : ""}
                        {w.change_pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%
                      </span>
                      <span>{w.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <table className="w-full text-left text-xs text-slate-400">
              <thead>
                <tr className="border-b border-slate-700 text-slate-500">
                  <th className="py-2 pr-2">Tipo</th>
                  <th className="py-2 pr-2">Código</th>
                  <th className="py-2 pr-2">Descrição</th>
                  <th className="py-2 pr-2">Und</th>
                  <th className="py-2 pr-2 text-right">Coef.</th>
                  <th className="py-2 pr-2 text-right">
                    Preço un. {previewPriceMode === "comd" ? "(ComD)" : "(SemD)"}
                  </th>
                  <th className="py-2 text-right">
                    Parcial {previewPriceMode === "comd" ? "(ComD)" : "(SemD)"}
                  </th>
                </tr>
              </thead>
              <tbody>
                {preview.items.map((item, i) => {
                  const unitPrice =
                    previewPriceMode === "semd"
                      ? item.unit_price_sem ?? item.unit_price
                      : item.unit_price;
                  const partialCost =
                    previewPriceMode === "semd"
                      ? item.partial_cost_sem ?? item.partial_cost
                      : item.partial_cost;
                  return (
                    <tr key={`${item.code}-${i}`} className="border-b border-slate-800/80">
                      <td className="py-1.5 pr-2 capitalize text-cyan-400/90">{item.item_type.replace("_", " ")}</td>
                      <td className="py-1.5 pr-2 font-mono">{item.code}</td>
                      <td className="py-1.5 pr-2">{item.description}</td>
                      <td className="py-1.5 pr-2">{item.unit}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{item.coefficient}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">
                        {unitPrice.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-1.5 text-right tabular-nums">
                        {partialCost.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {preview.items.length === 0 && (
              <p className="text-sm text-amber-400/90">
                Composição sem detalhamento analítico nesta base — importe a planilha com aba Analítico (SINAPI) ou
                outra fonte compatível.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
