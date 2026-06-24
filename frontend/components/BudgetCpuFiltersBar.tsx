"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BudgetPriceBaseSelection, PriceBankReference } from "@/types/api";
import { BRAZIL_UFS, referenceLabelFromKey } from "@/lib/brazil-ufs";
import {
  SICRO_REGIONS,
  sicroReferenceMatchesUf,
  sicroUfsForRegion,
} from "@/lib/sicro-links";
import { budgetBtn, budgetFieldLabel, budgetSelect } from "@/lib/budget-ui";
import { cn } from "@/lib/utils";

function sourceKey(ref: PriceBankReference): string {
  return (ref.source || "sinapi").toLowerCase();
}

function isSeminfSource(source: string): boolean {
  const s = source.toLowerCase();
  return s === "dp_seminf" || s === "ppd_seminf";
}

export const SOURCE_LABELS: Record<string, string> = {
  sinapi: "SINAPI",
  dp_seminf: "DP/SEMINF",
  ppd_seminf: "PP/SEMINF",
  cicro: "CICRO/SICRO",
};

function sourceLabel(name: string, references: PriceBankReference[]): string {
  if (SOURCE_LABELS[name]) return SOURCE_LABELS[name];
  const ref = references.find((r) => sourceKey(r) === name);
  if (ref?.source) {
    const key = sourceKey({ ...ref, source: ref.source });
    if (SOURCE_LABELS[key]) return SOURCE_LABELS[key];
  }
  return name.replace(/_/g, " ").toUpperCase();
}

export interface BudgetCpuFilterState {
  source: string;
  reference: string;
  uf: string;
  region: string;
  references: PriceBankReference[];
  loading: boolean;
  error: string | null;
  setSource: (source: string) => void;
  changeSource: (source: string) => void;
  setReference: (reference: string) => void;
  setUf: (uf: string) => void;
  setRegion: (region: string) => void;
  sourceOptions: Array<{ name: string; label: string }>;
  periodOptions: PriceBankReference[];
  ufOptions: string[];
}

export function useBudgetCpuFilters(
  priceBases: BudgetPriceBaseSelection[] = []
): BudgetCpuFilterState {
  const [references, setReferences] = useState<PriceBankReference[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState("sinapi");
  const [reference, setReference] = useState("");
  const [uf, setUf] = useState("SP");
  const [region, setRegion] = useState("all");

  useEffect(() => {
    api
      .pricingSyncBankReferences()
      .then((res) => setReferences(res.references ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao carregar períodos"))
      .finally(() => setLoading(false));
  }, []);

  const enabledBases = useMemo(
    () => priceBases.filter((b) => b.enabled && b.reference),
    [priceBases]
  );

  useEffect(() => {
    if (references.length === 0) return;
    const primary = enabledBases[0];
    if (primary) {
      setSource(primary.source);
      setReference(primary.reference);
      setUf(primary.uf);
      return;
    }
    const firstSinapi = references.find((r) => sourceKey(r) === "sinapi");
    if (firstSinapi) {
      setSource(sourceKey(firstSinapi));
      setReference(firstSinapi.reference);
      setUf(firstSinapi.default_uf ?? "SP");
    }
  }, [references, enabledBases]);

  const sourceOptions = useMemo(() => {
    const names = new Set<string>();
    for (const r of references) {
      names.add(sourceKey(r));
    }
    return Array.from(names).map((name) => ({
      name,
      label: sourceLabel(name, references),
    }));
  }, [references]);

  const periodOptions = useMemo(() => {
    if (source === "cicro") {
      return references.filter(
        (r) =>
          (sourceKey(r) === "cicro" || r.reference.toUpperCase().includes("SICRO")) &&
          sicroReferenceMatchesUf(r.reference, uf)
      );
    }
    if (isSeminfSource(source)) {
      return references.filter((r) => isSeminfSource(sourceKey(r)));
    }
    return references.filter((r) => sourceKey(r) === source);
  }, [references, source, uf]);

  const changeSource = useCallback(
    (src: string) => {
      setSource(src);
      setUf(src === "cicro" || isSeminfSource(src) ? "AM" : "SP");
      if (src === "cicro") setRegion("all");

      const refs =
        src === "cicro"
          ? references.filter(
              (r) =>
                (sourceKey(r) === "cicro" || r.reference.toUpperCase().includes("SICRO")) &&
                sicroReferenceMatchesUf(r.reference, src === "cicro" ? "AM" : uf)
            )
          : isSeminfSource(src)
            ? references.filter((r) => isSeminfSource(sourceKey(r)))
            : references.filter((r) => sourceKey(r) === src);

      if (refs[0]) setReference(refs[0].reference);
    },
    [references, uf]
  );

  useEffect(() => {
    if (periodOptions.length === 0) return;
    if (!periodOptions.some((r) => r.reference === reference)) {
      setReference(periodOptions[0].reference);
    }
  }, [periodOptions, reference]);

  const ufOptions = useMemo(() => {
    if (source === "cicro") return [...sicroUfsForRegion(region)];
    return [...BRAZIL_UFS];
  }, [source, region]);

  useEffect(() => {
    if (!ufOptions.includes(uf)) {
      setUf(ufOptions[0] ?? "SP");
    }
  }, [ufOptions, uf]);

  return {
    source,
    reference,
    uf,
    region,
    references,
    loading,
    error,
    setSource,
    changeSource,
    setReference,
    setUf,
    setRegion,
    sourceOptions,
    periodOptions,
    ufOptions,
  };
}

interface BudgetCpuFiltersBarProps {
  filters: BudgetCpuFilterState;
  disabled?: boolean;
  extra?: React.ReactNode;
}

export function BudgetCpuFiltersBar({ filters, disabled, extra }: BudgetCpuFiltersBarProps) {
  const {
    source,
    reference,
    uf,
    region,
    setSource,
    setReference,
    setUf,
    setRegion,
    sourceOptions,
    periodOptions,
    ufOptions,
    loading,
    error,
  } = filters;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-3">
        {sourceOptions.length > 0 && (
          <label className="text-sm text-slate-400">
            <span className={budgetFieldLabel}>Tipo de base</span>
            <select
              value={source}
              disabled={disabled || loading}
              onChange={(e) => {
                filters.changeSource(e.target.value);
              }}
              className={cn(budgetSelect, "min-w-[160px]")}
            >
              {sourceOptions.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        )}
        {periodOptions.length > 0 && (
          <label className="text-sm text-slate-400">
            <span className={budgetFieldLabel}>Período</span>
            <select
              value={reference}
              disabled={disabled || loading}
              onChange={(e) => setReference(e.target.value)}
              className={cn(budgetSelect, "min-w-[180px]")}
            >
              {periodOptions.map((r) => (
                <option key={r.reference} value={r.reference}>
                  {r.label ?? referenceLabelFromKey(r.reference)}
                </option>
              ))}
            </select>
          </label>
        )}
        {source === "cicro" && (
          <label className="text-sm text-slate-400">
            <span className={budgetFieldLabel}>Região</span>
            <select
              value={region}
              disabled={disabled || loading}
              onChange={(e) => setRegion(e.target.value)}
              className={cn(budgetSelect, "min-w-[120px]")}
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
          <span className={budgetFieldLabel}>UF</span>
          <select
            value={uf}
            disabled={disabled || loading}
            onChange={(e) => setUf(e.target.value)}
            className={cn(budgetSelect, "min-w-[72px]")}
          >
            {ufOptions.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>
        {extra}
      </div>
      {error && <p className="text-xs text-red-300">{error}</p>}
    </div>
  );
}

export function BudgetCpuFilterButton({
  onClick,
  disabled,
  loading,
  label = "Consultar",
}: {
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className={cn(
        budgetBtn,
        "bg-cyan-600/25 text-cyan-200 ring-cyan-500/40 hover:bg-cyan-600/35"
      )}
    >
      {loading ? "Carregando…" : label}
    </button>
  );
}
