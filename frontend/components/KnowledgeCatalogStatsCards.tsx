"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type {
  KnowledgeCatalogEntry,
  KnowledgeOptionsResponse,
  KnowledgeStatsResponse,
} from "@/types/api";

const CONTENT_TYPE_COLORS: Record<string, string> = {
  nbrs: "from-blue-500/15 to-blue-600/5 ring-blue-500/25 text-blue-300",
  sinapi: "from-emerald-500/15 to-emerald-600/5 ring-emerald-500/25 text-emerald-300",
  tcpo: "from-amber-500/15 to-amber-600/5 ring-amber-500/25 text-amber-300",
  tdrs: "from-violet-500/15 to-violet-600/5 ring-violet-500/25 text-violet-300",
  catalogos: "from-pink-500/15 to-pink-600/5 ring-pink-500/25 text-pink-300",
  manuais: "from-teal-500/15 to-teal-600/5 ring-teal-500/25 text-teal-300",
  projetos: "from-indigo-500/15 to-indigo-600/5 ring-indigo-500/25 text-indigo-300",
  regional: "from-orange-500/15 to-orange-600/5 ring-orange-500/25 text-orange-300",
  modelos_orcamento: "from-fuchsia-500/15 to-fuchsia-600/5 ring-fuchsia-500/25 text-fuchsia-300",
  bases_precos: "from-lime-500/15 to-lime-600/5 ring-lime-500/25 text-lime-300",
};

const INDEX_BASE_COLORS: Record<string, string> = {
  nbr: "text-blue-300",
  sinapi: "text-emerald-300",
  tcpo: "text-amber-300",
  tdr: "text-violet-300",
  catalogos: "text-pink-300",
  regional: "text-orange-300",
  budget_models: "text-fuchsia-300",
};

interface KnowledgeCatalogStatsCardsProps {
  stats: KnowledgeStatsResponse | null;
  catalog: KnowledgeCatalogEntry[];
  options?: KnowledgeOptionsResponse | null;
}

function labelForContentType(
  value: string,
  options?: KnowledgeOptionsResponse | null
): string {
  const fromOptions = options?.content_types?.find((ct) => ct.value === value)?.label;
  if (fromOptions) return fromOptions;
  if (value === "unknown" || !value) return "Sem tipo";
  return value.replace(/_/g, " ");
}

function SummaryCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl bg-slate-950/50 p-4 ring-1 ring-slate-800">
      <p className={cn("text-2xl font-bold tabular-nums text-white", accent)}>{value}</p>
      <p className="mt-1 text-xs font-medium text-slate-400">{label}</p>
      {hint && <p className="mt-0.5 text-[11px] text-slate-600">{hint}</p>}
    </div>
  );
}

function TypeCard({
  label,
  count,
  total,
  colorClass,
}: {
  label: string;
  count: number;
  total: number;
  colorClass: string;
}) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div
      className={cn(
        "rounded-xl bg-gradient-to-br p-4 ring-1",
        colorClass || "from-slate-800/40 to-slate-900/20 ring-slate-700/50 text-slate-300"
      )}
    >
      <p className="text-xl font-bold tabular-nums">{count.toLocaleString("pt-BR")}</p>
      <p className="mt-1 text-xs font-medium leading-snug opacity-90">{label}</p>
      <div className="mt-3 h-1 overflow-hidden rounded-full bg-black/20">
        <div
          className="h-full rounded-full bg-current opacity-60"
          style={{ width: `${Math.max(pct, count > 0 ? 4 : 0)}%` }}
        />
      </div>
      <p className="mt-1 text-[10px] opacity-70">{pct}% do acervo</p>
    </div>
  );
}

export default function KnowledgeCatalogStatsCards({
  stats,
  catalog,
  options,
}: KnowledgeCatalogStatsCardsProps) {
  const derived = useMemo(() => {
    const priceBases = catalog.filter((i) => i.has_price_items).length;
    const activePriceBases = catalog.filter((i) => i.is_active_price_base).length;
    const budgetModels = catalog.filter((i) => i.has_budget_model).length;
    const totalPriceItems = catalog.reduce((sum, i) => sum + (i.price_item_count ?? 0), 0);
    return { priceBases, activePriceBases, budgetModels, totalPriceItems };
  }, [catalog]);

  const byType = useMemo(() => {
    const fromStats = stats?.by_content_type ?? {};
    const entries = Object.entries(fromStats)
      .map(([value, count]) => ({
        value,
        count,
        label: labelForContentType(value, options),
      }))
      .sort((a, b) => b.count - a.count);
    return entries;
  }, [stats?.by_content_type, options]);

  const indexChunks = stats?.index?.multi_index ?? {};
  const indexNames = stats?.index?.index_names ?? {};
  const totalDocs = stats?.catalog_total ?? catalog.length;
  const totalChunks = stats?.index?.total_multi_chunks ?? 0;
  const logEntries = stats?.catalog_log_entries;
  const supersededEntries = stats?.catalog_superseded ?? 0;
  const norms = stats?.norms;

  if (!stats && catalog.length === 0) {
    return null;
  }

  return (
    <div className="mt-6 space-y-6 border-t border-slate-800/80 pt-6">
      <div>
        <h4 className="text-sm font-semibold text-white">Resumo do acervo</h4>
        <p className="mt-0.5 text-xs text-slate-500">
          Totais do catálogo central e cobertura dos índices FAISS para busca pela IA.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Documentos ativos"
          value={totalDocs.toLocaleString("pt-BR")}
          hint="Versão vigente no catálogo (deduplicada)"
          accent="text-white"
        />
        <SummaryCard
          label="Entradas no log"
          value={(logEntries ?? totalDocs).toLocaleString("pt-BR")}
          hint={
            supersededEntries > 0
              ? `${supersededEntries.toLocaleString("pt-BR")} substituídas por versão mais nova`
              : "Histórico completo de importações"
          }
        />
        <SummaryCard
          label="Chunks FAISS (IA)"
          value={totalChunks.toLocaleString("pt-BR")}
          hint="Trechos indexados para RAG"
          accent="text-cyan-400"
        />
        <SummaryCard
          label="Bases de preço"
          value={derived.priceBases.toLocaleString("pt-BR")}
          hint={
            derived.activePriceBases
              ? `${derived.activePriceBases} ativa(s) · ${derived.totalPriceItems.toLocaleString("pt-BR")} itens`
              : derived.totalPriceItems
                ? `${derived.totalPriceItems.toLocaleString("pt-BR")} itens de preço`
                : "SINAPI / TCPO / bases"
          }
          accent="text-emerald-400"
        />
        <SummaryCard
          label="Modelos WBS (PPD)"
          value={derived.budgetModels.toLocaleString("pt-BR")}
          hint="Planilhas com serviços para orçamento"
          accent="text-violet-400"
        />
      </div>

      {norms && norms.total > 0 && (
        <div>
          <h4 className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">
            Normas técnicas (NBR / NR)
          </h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <SummaryCard
              label="Total de normas"
              value={norms.total.toLocaleString("pt-BR")}
              hint={`${norms.nbr_count.toLocaleString("pt-BR")} NBR · ${norms.nr_count.toLocaleString("pt-BR")} NR`}
              accent="text-blue-300"
            />
            <SummaryCard
              label="Vigentes / atualizadas"
              value={norms.current_count.toLocaleString("pt-BR")}
              hint="Não marcadas como acervo histórico"
              accent="text-emerald-300"
            />
            <SummaryCard
              label="Acervo histórico"
              value={norms.historical_count.toLocaleString("pt-BR")}
              hint="Marcadas edition_outdated na importação"
              accent="text-amber-300"
            />
            <SummaryCard
              label="Sem ano identificado"
              value={norms.without_year_count.toLocaleString("pt-BR")}
              hint="Revise o nome do arquivo ou sidecar"
              accent="text-slate-400"
            />
            <SummaryCard
              label="Códigos NBR únicos"
              value={norms.unique_codes.toLocaleString("pt-BR")}
              hint="Ex.: 6118, 9050, 5410"
              accent="text-blue-300"
            />
            <SummaryCard
              label="NBRs com várias edições"
              value={norms.multi_edition_codes.toLocaleString("pt-BR")}
              hint="Mesmo número, anos de revisão diferentes"
              accent="text-orange-300"
            />
            <SummaryCard
              label="Edições distintas"
              value={norms.unique_editions.toLocaleString("pt-BR")}
              hint="Pares código + ano no acervo"
              accent="text-cyan-300"
            />
            <SummaryCard
              label="Anos de revisão"
              value={norms.distinct_years.toLocaleString("pt-BR")}
              hint="Anos únicos encontrados nos PDFs"
              accent="text-violet-300"
            />
          </div>
        </div>
      )}

      {byType.length > 0 && (
        <div>
          <h4 className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">
            Por tipo de conteúdo
          </h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {byType.map(({ value, count, label }) => (
              <TypeCard
                key={value || "unknown"}
                label={label}
                count={count}
                total={totalDocs}
                colorClass={CONTENT_TYPE_COLORS[value] ?? ""}
              />
            ))}
          </div>
        </div>
      )}

      {Object.keys(indexChunks).length > 0 && (
        <div>
          <h4 className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">
            Chunks por índice FAISS
          </h4>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Object.entries(indexChunks)
              .sort(([, a], [, b]) => b - a)
              .map(([base, chunks]) => {
                const baseLabel =
                  options?.bases?.find((b) => b.value === base)?.label ??
                  indexNames[base] ??
                  base.toUpperCase();
                return (
                  <div
                    key={base}
                    className="flex items-center justify-between rounded-lg bg-slate-950/60 px-4 py-3 ring-1 ring-slate-800"
                  >
                    <span className="text-sm text-slate-300">{baseLabel}</span>
                    <span
                      className={cn(
                        "text-lg font-semibold tabular-nums",
                        INDEX_BASE_COLORS[base] ?? "text-slate-200"
                      )}
                    >
                      {chunks.toLocaleString("pt-BR")}
                    </span>
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}
