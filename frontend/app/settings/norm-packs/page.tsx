"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/services/api";
import type {
  NormPackAnalyzeResponse,
  NormPackListItem,
  NormPackNbrPreviewItem,
  NormPackPreviewResponse,
} from "@/types/api";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  indexed: { label: "Indexada", className: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30" },
  not_indexed: { label: "PDF presente — indexar", className: "bg-amber-500/15 text-amber-300 ring-amber-500/30" },
  missing: { label: "Upload necessário", className: "bg-red-500/15 text-red-300 ring-red-500/30" },
};

const LEGAL_SOURCE_LABEL: Record<string, string> = {
  abnt_licensed_pdf: "PDF licenciado (ABNT)",
  public_legislation: "Legislação pública",
  missing: "—",
};

function NbrPreviewPanel({
  item,
  notice,
  onClose,
}: {
  item: NormPackNbrPreviewItem;
  notice: string;
  onClose: () => void;
}) {
  return (
    <div className="flex h-full flex-col rounded-2xl bg-slate-950/80 ring-1 ring-slate-700">
      <div className="flex items-start justify-between gap-3 border-b border-slate-800 px-4 py-3">
        <div>
          <p className="font-mono text-sm text-cyan-300">NBR {item.nbr_code}</p>
          <p className="text-sm text-slate-300">{item.title}</p>
          {item.filename && (
            <p className="mt-1 truncate text-xs text-slate-500" title={item.filename}>
              {item.filename}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 rounded-lg px-2 py-1 text-xs text-slate-400 ring-1 ring-slate-700 hover:bg-slate-800"
        >
          Fechar
        </button>
      </div>
      <p className="border-b border-slate-800 px-4 py-2 text-xs text-slate-500">{notice}</p>
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {item.chunks.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhum trecho disponível.</p>
        ) : (
          item.chunks.map((chunk) => (
            <article
              key={chunk.chunk_index}
              className="rounded-xl bg-slate-900/60 p-3 ring-1 ring-slate-800"
            >
              <p className="mb-2 text-xs text-slate-500">
                Trecho #{chunk.chunk_index + 1}
                {chunk.page != null ? ` · pág. ${chunk.page}` : ""}
                {chunk.char_count ? ` · ${chunk.char_count} caracteres` : ""}
              </p>
              <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-slate-300">
                {chunk.text}
              </pre>
            </article>
          ))
        )}
        {item.chunk_count > item.chunks.length && (
          <p className="text-center text-xs text-slate-500">
            Exibindo {item.chunks.length} de {item.chunk_count} trechos indexados.
          </p>
        )}
      </div>
    </div>
  );
}

export default function SettingsNormPacksPage() {
  const [packs, setPacks] = useState<NormPackListItem[]>([]);
  const [legalNotice, setLegalNotice] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [analysis, setAnalysis] = useState<NormPackAnalyzeResponse | null>(null);
  const [preview, setPreview] = useState<NormPackPreviewResponse | null>(null);
  const [previewNbr, setPreviewNbr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadPacks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.knowledgeNormPacks();
      setPacks(data.packs);
      setLegalNotice(data.legal_notice);
      setSelectedId((prev) => prev || data.packs[0]?.id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar pacotes");
    } finally {
      setLoading(false);
    }
  }, []);

  const runAnalyze = useCallback(async (packId: string) => {
    if (!packId) return;
    setAnalyzing(true);
    setError(null);
    setMessage(null);
    setPreview(null);
    setPreviewNbr(null);
    try {
      const data = await api.knowledgeNormPackAnalyze(packId);
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na análise");
      setAnalysis(null);
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const loadPreview = useCallback(
    async (packId: string, nbrCode?: string) => {
      if (!packId) return;
      setPreviewLoading(true);
      setError(null);
      try {
        const data = await api.knowledgeNormPackPreview(packId, nbrCode);
        setPreview(data);
        setPreviewNbr(nbrCode ?? data.items[0]?.nbr_code ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Falha ao carregar preview");
        setPreview(null);
      } finally {
        setPreviewLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    loadPacks();
  }, [loadPacks]);

  useEffect(() => {
    if (selectedId) runAnalyze(selectedId);
  }, [selectedId, runAnalyze]);

  const handleIndex = async (force = false) => {
    if (!selectedId) return;
    setIndexing(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.knowledgeNormPackIndex(selectedId, force);
      const indexed = result.results.filter((r) => r.status === "indexed").length;
      setMessage(
        `Indexação concluída: ${result.indexed_chunks} chunks novos · ${indexed} norma(s) processada(s).`
      );
      await runAnalyze(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na indexação");
    } finally {
      setIndexing(false);
    }
  };

  const handlePreviewAll = () => {
    if (!selectedId) return;
    loadPreview(selectedId);
  };

  const handlePreviewOne = (nbrCode: string) => {
    if (!selectedId) return;
    setPreviewNbr(nbrCode);
    loadPreview(selectedId, nbrCode);
  };

  if (loading) {
    return <p className="text-sm text-slate-500">Carregando pacotes normativos…</p>;
  }

  const summary = analysis?.summary;
  const selectedPack = packs.find((p) => p.id === selectedId);
  const transversalPacks = packs.filter(
    (p) => p.group === "transversal" || p.group === "composto" || !p.group?.startsWith("disc")
  );
  const disciplinePacks = packs.filter((p) => p.group === "disciplina" || p.id.startsWith("disc_"));
  const indexedCount = summary?.indexed ?? 0;
  const activePreviewItem =
    preview?.items.find((i) => i.nbr_code === previewNbr) ?? preview?.items[0] ?? null;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-700/60 bg-slate-900/50 p-5">
        <h2 className="text-sm font-semibold text-slate-200">Conformidade comercial</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">{legalNotice}</p>
      </section>

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0 flex-1">
            <label htmlFor="norm-pack" className="block text-sm font-medium text-slate-300">
              Pacote normativo
            </label>
            <select
              id="norm-pack"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="mt-2 w-full max-w-lg rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              {(transversalPacks.length > 0 || disciplinePacks.length === 0) && (
                <optgroup label="Pacotes transversais">
                  {(transversalPacks.length > 0 ? transversalPacks : packs).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label} ({p.item_count} NBRs)
                    </option>
                  ))}
                </optgroup>
              )}
              {disciplinePacks.length > 0 && (
                <optgroup label="Por disciplina (agentes)">
                  {disciplinePacks.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label} ({p.item_count} NBRs)
                      {p.agent_slug ? ` · ${p.agent_slug}` : ""}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            {selectedPack?.agent_slug && (
              <p className="mt-1 text-xs text-cyan-400/80">
                Agente: {selectedPack.agent_slug}_agent · {selectedPack.discipline}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!selectedId || analyzing}
              onClick={() => runAnalyze(selectedId)}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200 ring-1 ring-slate-700 disabled:opacity-50"
            >
              {analyzing ? "Analisando…" : "Atualizar gap"}
            </button>
            <button
              type="button"
              disabled={!selectedId}
              onClick={() => api.downloadNormPackGapCsv(selectedId).catch((e) => setError(String(e)))}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200 ring-1 ring-slate-700 disabled:opacity-50"
            >
              Exportar CSV
            </button>
            <button
              type="button"
              disabled={!selectedId || previewLoading || indexedCount === 0}
              onClick={handlePreviewAll}
              className="rounded-lg bg-violet-500/15 px-4 py-2 text-sm font-medium text-violet-300 ring-1 ring-violet-500/35 disabled:opacity-50"
            >
              {previewLoading && !previewNbr ? "Carregando…" : "Preview indexadas"}
            </button>
            <button
              type="button"
              disabled={!selectedId || indexing}
              onClick={() => handleIndex(false)}
              className="rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-300 ring-1 ring-cyan-500/40 disabled:opacity-50"
            >
              {indexing ? "Indexando…" : "Indexar pacote"}
            </button>
          </div>
        </div>

        {summary && (
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
            {[
              ["Cobertura", `${summary.coverage_pct}%`],
              ["Indexadas", String(summary.indexed)],
              ["Pendentes index", String(summary.not_indexed)],
              ["Faltando PDF", String(summary.missing)],
              ["Críticas faltando", String(summary.critical_missing)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl bg-slate-950/60 px-4 py-3 ring-1 ring-slate-800">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="text-lg font-semibold text-slate-100">{value}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {analysis && (
        <div
          className={cn(
            "grid gap-4",
            preview && activePreviewItem ? "lg:grid-cols-2" : "grid-cols-1"
          )}
        >
          <section className="overflow-hidden rounded-2xl ring-1 ring-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">NBR</th>
                  <th className="px-4 py-3">Título</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Chunks</th>
                  <th className="px-4 py-3">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-900/30">
                {analysis.items.map((item) => {
                  const st = STATUS_LABEL[item.status] ?? STATUS_LABEL.missing;
                  const isActive = previewNbr === item.nbr_code;
                  return (
                    <tr
                      key={item.nbr_code}
                      className={cn(
                        "text-slate-300",
                        isActive && "bg-violet-500/5"
                      )}
                    >
                      <td className="px-4 py-3 font-mono text-cyan-300/90">
                        NBR {item.nbr_code}
                        {item.critical && (
                          <span className="ml-2 text-[10px] uppercase text-amber-400">crítica</span>
                        )}
                      </td>
                      <td className="px-4 py-3">{item.title}</td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2 py-0.5 text-xs ring-1",
                            st.className
                          )}
                        >
                          {st.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono">{item.chunk_count}</td>
                      <td className="px-4 py-3">
                        {item.status === "indexed" ? (
                          <button
                            type="button"
                            disabled={previewLoading}
                            onClick={() => handlePreviewOne(item.nbr_code)}
                            className="rounded-md bg-violet-500/15 px-2 py-1 text-xs text-violet-300 ring-1 ring-violet-500/30 hover:bg-violet-500/25 disabled:opacity-50"
                          >
                            Preview
                          </button>
                        ) : (
                          <span className="text-xs text-slate-600">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>

          {preview && activePreviewItem && (
            <div className="min-h-[320px] lg:min-h-[480px]">
              {preview.items.length > 1 && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {preview.items.map((i) => (
                    <button
                      key={i.nbr_code}
                      type="button"
                      onClick={() => {
                        setPreviewNbr(i.nbr_code);
                        if (selectedId) loadPreview(selectedId, i.nbr_code);
                      }}
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs ring-1",
                        previewNbr === i.nbr_code
                          ? "bg-violet-500/20 text-violet-200 ring-violet-500/40"
                          : "bg-slate-900 text-slate-400 ring-slate-700"
                      )}
                    >
                      NBR {i.nbr_code}
                    </button>
                  ))}
                </div>
              )}
              <NbrPreviewPanel
                item={activePreviewItem}
                notice={preview.preview_notice}
                onClose={() => {
                  setPreview(null);
                  setPreviewNbr(null);
                }}
              />
            </div>
          )}
        </div>
      )}

      {summary && summary.missing > 0 && (
        <section className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
          <p className="text-sm text-amber-200/90">
            {summary.missing} norma(s) sem PDF licenciado. Faça upload em{" "}
            <Link href="/settings/imports" className="underline hover:text-amber-100">
              Importações
            </Link>
            .
          </p>
        </section>
      )}

      {message && <p className="text-sm text-emerald-400">{message}</p>}
      {error && <p className="text-sm text-red-300">{error}</p>}
    </div>
  );
}
