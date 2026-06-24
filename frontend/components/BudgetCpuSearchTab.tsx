"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import type { BudgetPriceBaseSelection, OpenCompositionDetail, OpenCompositionSummary } from "@/types/api";
import OpenCompositionLookupPanel from "@/components/OpenCompositionLookupPanel";
import { useBudgetCpuFilters } from "@/components/BudgetCpuFiltersBar";
import OpenCompositionPreview, { refLabelFromReference } from "@/components/OpenCompositionPreview";
import { formatBrl } from "@/lib/open-composition-ui";
import { referenceLabelFromKey } from "@/lib/brazil-ufs";
import { budgetInput } from "@/lib/budget-ui";
import { cn } from "@/lib/utils";

const MIN_QUERY_LEN = 2;
const DEBOUNCE_MS = 280;
const SEARCH_LIMIT = 20;

interface BudgetCpuSearchTabProps {
  priceBases?: BudgetPriceBaseSelection[];
}

export default function BudgetCpuSearchTab({ priceBases = [] }: BudgetCpuSearchTabProps) {
  const filters = useBudgetCpuFilters(priceBases);
  const [searchText, setSearchText] = useState("");
  const [results, setResults] = useState<OpenCompositionSummary[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchPreview, setSearchPreview] = useState<OpenCompositionDetail | null>(null);
  const [searchPreviewLoading, setSearchPreviewLoading] = useState(false);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [searchPriceMode, setSearchPriceMode] = useState<"comd" | "semd">("comd");
  const searchSeqRef = useRef(0);

  const periodLabel =
    filters.periodOptions.find((r) => r.reference === filters.reference)?.label ??
    referenceLabelFromKey(filters.reference);

  const openSearchResult = useCallback(
    async (code: string) => {
      if (!filters.reference) return;
      setSelectedCode(code);
      setSearchPreviewLoading(true);
      setSearchPreview(null);
      try {
        const comp = await api.pricingSyncOpenComposition(code, {
          uf: filters.uf,
          reference: filters.reference,
        });
        setSearchPreview(comp);
        setSearchError(null);
      } catch (e) {
        setSearchError(e instanceof Error ? e.message : "Falha ao abrir CPU");
      } finally {
        setSearchPreviewLoading(false);
      }
    },
    [filters.reference, filters.uf]
  );

  useEffect(() => {
    const q = searchText.trim();
    if (q.length < MIN_QUERY_LEN || !filters.reference || filters.loading) {
      setResults([]);
      setSearchError(null);
      setSearching(false);
      setSearchPreview(null);
      setSelectedCode(null);
      return;
    }

    const seq = ++searchSeqRef.current;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void (async () => {
        setSearching(true);
        setSearchError(null);
        try {
          const res = await api.pricingSyncSearchOpenCompositions(q, {
            reference: filters.reference,
            uf: filters.uf,
            limit: SEARCH_LIMIT,
            signal: controller.signal,
          });
          if (seq !== searchSeqRef.current) return;
          setResults(res.items);
          setSearchError(
            res.items.length === 0 ? "Nenhuma composição encontrada para este trecho." : null
          );
          setSearchPreview(null);
          setSelectedCode(null);
        } catch (e) {
          if (controller.signal.aborted) return;
          if (seq !== searchSeqRef.current) return;
          setSearchError(e instanceof Error ? e.message : "Falha na busca");
          setResults([]);
        } finally {
          if (seq === searchSeqRef.current) setSearching(false);
        }
      })();
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchText, filters.reference, filters.uf, filters.loading]);

  const showResultsPanel = searchText.trim().length >= MIN_QUERY_LEN;

  return (
    <div className="space-y-4">
      <OpenCompositionLookupPanel
        priceBases={priceBases}
        filters={filters}
        title="Prévia — composição aberta (CPU)"
        subtitle="Consulte CPUs por código. Escolha tipo de base, período e UF — igual ao módulo Bases de preços."
        codePlaceholder="Ex: 95995 ou 100087.1.9.SEMINF"
      />

      <div className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <h3 className="text-sm font-semibold text-slate-200">Busca por descrição</h3>
        <p className="mt-1 text-xs text-slate-500">
          Digite um trecho da descrição — os resultados aparecem automaticamente (mín. {MIN_QUERY_LEN}{" "}
          caracteres). Usa base, período e UF do painel acima.
        </p>
        <div className="mt-3">
          <label className="block text-sm text-slate-400">
            <span className="mb-1 flex items-center justify-between text-xs text-slate-500">
              <span>Trecho da descrição</span>
              {searching && <span className="text-cyan-400/80">Buscando…</span>}
            </span>
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Ex: pavimento asfáltico, container…"
              disabled={!filters.reference || filters.loading}
              className={cn(budgetInput, "w-full")}
              autoComplete="off"
              spellCheck={false}
            />
          </label>
        </div>

        {searchError && showResultsPanel && (
          <p className="mt-2 text-xs text-amber-300">{searchError}</p>
        )}

        {showResultsPanel && results.length > 0 && (
          <div className="mt-4 overflow-x-auto rounded-lg ring-1 ring-slate-800">
            <p className="border-b border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-500">
              {results.length} resultado(s) — clique para ver a CPU aberta
            </p>
            <table className="w-full text-left text-xs text-slate-400">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-500">
                  <th className="px-3 py-2">Código</th>
                  <th className="px-3 py-2">Descrição</th>
                  <th className="px-3 py-2">Und</th>
                  <th className="px-3 py-2 text-right">ComD</th>
                  <th className="px-3 py-2 text-right">SemD</th>
                  <th className="px-3 py-2">Match</th>
                </tr>
              </thead>
              <tbody>
                {results.map((row) => (
                  <tr
                    key={row.code}
                    onClick={() => void openSearchResult(row.code)}
                    className={cn(
                      "cursor-pointer border-b border-slate-800/80 hover:bg-cyan-500/5",
                      selectedCode === row.code && "bg-cyan-500/10"
                    )}
                  >
                    <td className="px-3 py-2 font-mono text-slate-200">{row.code}</td>
                    <td className="max-w-[min(100%,480px)] truncate px-3 py-2" title={row.description}>
                      {row.description}
                    </td>
                    <td className="px-3 py-2">{row.unit}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-emerald-300/90">
                      {formatBrl(row.total_price)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-cyan-300/90">
                      {formatBrl(row.total_price_sem)}
                    </td>
                    <td className="px-3 py-2 text-slate-500">
                      {row.match_kind === "code" ? "Código" : "Descrição"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {(searchPreview || searchPreviewLoading) && (
          <div className="mt-4 border-t border-slate-800 pt-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-slate-200">Prévia do resultado</h4>
              <label className="text-sm text-slate-400">
                Preços na tabela
                <select
                  value={searchPriceMode}
                  onChange={(e) => setSearchPriceMode(e.target.value as "comd" | "semd")}
                  className="ml-2 rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                >
                  <option value="comd">Com desoneração (ComD)</option>
                  <option value="semd">Sem desoneração (SemD)</option>
                </select>
              </label>
            </div>
            {searchPreviewLoading && <p className="text-sm text-slate-500">Carregando CPU…</p>}
            {searchPreview && (
              <OpenCompositionPreview
                preview={searchPreview}
                priceMode={searchPriceMode}
                referenceLabel={refLabelFromReference(filters.reference, periodLabel)}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
