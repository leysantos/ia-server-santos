"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BudgetPriceBaseSelection, OpenCompositionDetail } from "@/types/api";
import OpenCompositionPreview, { refLabelFromReference } from "@/components/OpenCompositionPreview";
import {
  type BudgetCpuFilterState,
  useBudgetCpuFilters,
} from "@/components/BudgetCpuFiltersBar";
import { referenceLabelFromKey } from "@/lib/brazil-ufs";
import { SICRO_REGIONS } from "@/lib/sicro-links";
import { cn } from "@/lib/utils";

const inlineSelect =
  "ml-2 rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 disabled:opacity-50";
const inlineInput =
  "rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700 placeholder:text-slate-500";

interface OpenCompositionLookupPanelProps {
  priceBases?: BudgetPriceBaseSelection[];
  filters?: BudgetCpuFilterState;
  title?: string;
  subtitle?: string;
  codePlaceholder?: string;
  className?: string;
}

export default function OpenCompositionLookupPanel({
  priceBases = [],
  filters: externalFilters,
  title = "Prévia — composição aberta (CPU)",
  subtitle = "Consulte CPUs por código. Escolha tipo de base, período e UF.",
  codePlaceholder = "Ex: 95995",
  className,
}: OpenCompositionLookupPanelProps) {
  const internalFilters = useBudgetCpuFilters(priceBases);
  const filters = externalFilters ?? internalFilters;
  const [code, setCode] = useState("");
  const [preview, setPreview] = useState<OpenCompositionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [priceMode, setPriceMode] = useState<"comd" | "semd">("comd");

  const periodLabel = useMemo(
    () =>
      filters.periodOptions.find((r) => r.reference === filters.reference)?.label ??
      referenceLabelFromKey(filters.reference),
    [filters.periodOptions, filters.reference]
  );

  const loadPreview = useCallback(
    async (opts?: { code?: string; uf?: string; reference?: string }) => {
      const queryCode = (opts?.code ?? code).trim();
      const queryRef = opts?.reference ?? filters.reference;
      const queryUf = opts?.uf ?? filters.uf;
      if (!queryCode || !queryRef) return;

      setLoading(true);
      setError(null);
      try {
        const comp = await api.pricingSyncOpenComposition(queryCode, {
          uf: queryUf,
          reference: queryRef,
        });
        setPreview(comp);
      } catch (e) {
        setPreview(null);
        setError(e instanceof Error ? e.message : "Composição não encontrada");
      } finally {
        setLoading(false);
      }
    },
    [code, filters.reference, filters.uf]
  );

  const handleSourceChange = (source: string) => {
    filters.changeSource(source);
    setPreview(null);
    setError(null);
  };

  const handleReferenceChange = (reference: string) => {
    filters.setReference(reference);
    if (preview && code.trim()) {
      void loadPreview({ reference });
    }
  };

  const handleUfChange = (uf: string) => {
    filters.setUf(uf);
    if (preview && code.trim()) {
      void loadPreview({ uf });
    }
  };

  const handleRegionChange = (region: string) => {
    filters.setRegion(region);
  };

  useEffect(() => {
    if (!preview || !code.trim()) return;
    void loadPreview();
    // Recarrega prévia ao mudar período (UF dispara via handleUfChange).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.reference]);

  const canConsult = Boolean(code.trim() && filters.reference && !filters.loading);

  return (
    <section className={cn("rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800", className)}>
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      <p className="mt-1 text-xs text-slate-500">{subtitle}</p>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && canConsult) void loadPreview();
          }}
          placeholder={codePlaceholder}
          disabled={loading || filters.loading}
          className={inlineInput}
        />

        {filters.sourceOptions.length > 0 && (
          <label className="text-sm text-slate-400">
            Tipo de base
            <select
              value={filters.source}
              onChange={(e) => handleSourceChange(e.target.value)}
              disabled={loading || filters.loading}
              className={inlineSelect}
            >
              {filters.sourceOptions.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        )}

        {filters.periodOptions.length > 0 && (
          <label className="text-sm text-slate-400">
            Período
            <select
              value={filters.reference}
              onChange={(e) => handleReferenceChange(e.target.value)}
              disabled={loading || filters.loading}
              className={inlineSelect}
            >
              {filters.periodOptions.map((r) => (
                <option key={r.reference} value={r.reference}>
                  {r.label ?? referenceLabelFromKey(r.reference)}
                </option>
              ))}
            </select>
          </label>
        )}

        {filters.source === "cicro" && (
          <label className="text-sm text-slate-400">
            Região
            <select
              value={filters.region}
              onChange={(e) => handleRegionChange(e.target.value)}
              disabled={loading || filters.loading}
              className={inlineSelect}
            >
              <option value="all">Todas</option>
              {SICRO_REGIONS.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="text-sm text-slate-400">
          UF
          <select
            value={filters.uf}
            onChange={(e) => handleUfChange(e.target.value)}
            disabled={loading || filters.loading}
            className={inlineSelect}
          >
            {filters.ufOptions.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={() => void loadPreview()}
          disabled={loading || filters.loading || !canConsult}
          className="rounded-lg bg-cyan-700/80 px-4 py-2 text-sm text-white hover:bg-cyan-600 disabled:opacity-50"
        >
          {loading ? "Carregando…" : "Consultar"}
        </button>

        {preview && (
          <label className="text-sm text-slate-400">
            Preços na tabela
            <select
              value={priceMode}
              onChange={(e) => setPriceMode(e.target.value as "comd" | "semd")}
              className={inlineSelect}
            >
              <option value="comd">Com desoneração (ComD)</option>
              <option value="semd">Sem desoneração (SemD)</option>
            </select>
          </label>
        )}
      </div>

      {filters.error && <p className="mt-2 text-xs text-red-300">{filters.error}</p>}
      {error && <p className="mt-2 text-xs text-amber-300">{error}</p>}

      {preview && (
        <div className="mt-4">
          <OpenCompositionPreview
            preview={preview}
            priceMode={priceMode}
            referenceLabel={refLabelFromReference(filters.reference, periodLabel)}
          />
        </div>
      )}
    </section>
  );
}