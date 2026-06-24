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
import { cn } from "@/lib/utils";
import { budgetBtn, budgetSelect } from "@/lib/budget-ui";

const ADDABLE_BASES: Array<{ source: string; label: string }> = [
  { source: "sinapi", label: "SINAPI" },
  { source: "dp_seminf", label: "DP/SEMINF" },
  { source: "cicro", label: "SICRO3" },
];

function isSeminfSource(source: string): boolean {
  const s = source.toLowerCase();
  return s === "dp_seminf" || s === "ppd_seminf";
}

function sourceKey(ref: PriceBankReference): string {
  return (ref.source || "sinapi").toLowerCase();
}

function refsForBase(
  source: string,
  uf: string,
  references: PriceBankReference[]
): PriceBankReference[] {
  if (source === "sinapi") {
    return references.filter((r) => sourceKey(r) === "sinapi");
  }
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
  return [];
}

function refLabel(row: BudgetPriceBaseSelection, references: PriceBankReference[]) {
  const match = refsForBase(row.source, row.uf, references).find((r) => r.reference === row.reference);
  return match?.label ?? referenceLabelFromKey(row.reference);
}

interface BudgetPriceBasesPanelProps {
  value: BudgetPriceBaseSelection[];
  disabled?: boolean;
  onChange: (next: BudgetPriceBaseSelection[]) => void;
}

export default function BudgetPriceBasesPanel({ value, disabled, onChange }: BudgetPriceBasesPanelProps) {
  const [references, setReferences] = useState<PriceBankReference[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draftSource, setDraftSource] = useState("sinapi");
  const [draftUf, setDraftUf] = useState("SP");
  const [draftRegion, setDraftRegion] = useState("all");
  const [draftReference, setDraftReference] = useState("");
  const [editingSource, setEditingSource] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    api
      .pricingSyncBankReferences()
      .then((res) => setReferences(res.references ?? []))
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Falha ao carregar períodos"));
  }, []);

  const sinapiImported = references.some((r) => sourceKey(r) === "sinapi");
  const seminfImported = references.some((r) => isSeminfSource(sourceKey(r)));
  const cicroImported = references.some(
    (r) => sourceKey(r) === "cicro" || r.reference.toUpperCase().includes("SICRO")
  );

  const cicroUfOptions = useMemo(() => [...sicroUfsForRegion(draftRegion)], [draftRegion]);

  const draftRefs = useMemo(
    () => refsForBase(draftSource, draftUf, references),
    [draftSource, draftUf, references]
  );

  useEffect(() => {
    if (!draftRefs.some((r) => r.reference === draftReference)) {
      setDraftReference(draftRefs[0]?.reference ?? "");
    }
  }, [draftRefs, draftReference]);

  const activeBases = useMemo(
    () => value.filter((b) => b.enabled && b.reference),
    [value]
  );

  const resetDraft = useCallback((source = "sinapi") => {
    setDraftSource(source);
    setDraftUf(source === "cicro" ? "AM" : "SP");
    setDraftRegion("all");
    setEditingSource(null);
    setFormError(null);
  }, []);

  const buildSelection = useCallback((): BudgetPriceBaseSelection | null => {
    const label = ADDABLE_BASES.find((b) => b.source === draftSource)?.label ?? draftSource.toUpperCase();
    if (!draftReference) {
      setFormError("Selecione um período importado.");
      return null;
    }
    if (draftSource === "sinapi" && !sinapiImported) {
      setFormError("Importe SINAPI em Configurações → Bases de preços.");
      return null;
    }
    if (isSeminfSource(draftSource) && !seminfImported) {
      setFormError("Importe DP/SEMINF em Configurações → Bases de preços.");
      return null;
    }
    if (draftSource === "cicro" && !cicroImported) {
      setFormError("Importe SICRO em Configurações → Bases de preços.");
      return null;
    }
    return {
      source: draftSource,
      label,
      enabled: true,
      uf: draftUf.toUpperCase(),
      reference: draftReference,
    };
  }, [cicroImported, draftReference, draftSource, draftUf, seminfImported, sinapiImported]);

  const handleAdd = () => {
    const sel = buildSelection();
    if (!sel) return;
    if (value.some((b) => b.source === sel.source && b.enabled)) {
      setFormError(`A base ${sel.label} já está no orçamento. Use Editar para alterar o período.`);
      return;
    }
    onChange([...value.filter((b) => b.source !== sel.source), sel]);
    resetDraft();
  };

  const handleSaveEdit = () => {
    const sel = buildSelection();
    if (!sel || !editingSource) return;
    onChange(value.map((b) => (b.source === editingSource ? sel : b)));
    resetDraft();
  };

  const handleStartEdit = (row: BudgetPriceBaseSelection) => {
    setEditingSource(row.source);
    setDraftSource(row.source);
    setDraftUf(row.uf);
    setDraftReference(row.reference);
    setFormError(null);
  };

  const handleRemove = (source: string) => {
    onChange(value.filter((b) => b.source !== source));
    if (editingSource === source) resetDraft();
  };

  const fieldLabel = "block text-xs text-slate-500 mb-1";

  return (
    <div className="overflow-hidden rounded-xl bg-slate-900/40 ring-1 ring-slate-800">
      <div className="border-b border-slate-800 px-5 py-4">
        <h3 className="text-sm font-semibold text-slate-200">Bases de preços do orçamento</h3>
        <p className="mt-1 text-xs text-slate-500">
          Adicione as bases usadas na composição manual e por IA. Escolha o período de cada base no
          orçamento — inclusive bases antigas para aditivos. Períodos devem estar importados em{" "}
          <a href="/settings/price-bases" className="text-cyan-400 underline">
            Configurações → Bases de preços
          </a>
          .
        </p>
        {loadError && <p className="mt-2 text-xs text-red-300">{loadError}</p>}
      </div>

      <div className="border-b border-slate-800 px-5 py-4">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
          {editingSource ? "Editar base" : "Adicionar base"}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-400">
            <span className={fieldLabel}>Tipo de base</span>
            <select
              value={draftSource}
              disabled={disabled || !!editingSource}
              onChange={(e) => {
                const src = e.target.value;
                setDraftSource(src);
                setDraftUf(src === "cicro" ? "AM" : src === "dp_seminf" ? "AM" : "SP");
                setFormError(null);
              }}
              className={cn(budgetSelect, "min-w-[160px]")}
            >
              {ADDABLE_BASES.map((b) => (
                <option key={b.source} value={b.source}>
                  {b.label}
                </option>
              ))}
            </select>
          </label>

          {draftSource === "cicro" && (
            <label className="text-sm text-slate-400">
              <span className={fieldLabel}>Região</span>
              <select
                value={draftRegion}
                disabled={disabled}
                onChange={(e) => {
                  setDraftRegion(e.target.value);
                  const ufs = sicroUfsForRegion(e.target.value);
                  if (!ufs.includes(draftUf as (typeof ufs)[number])) {
                    setDraftUf(ufs[0] ?? draftUf);
                  }
                }}
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
            <span className={fieldLabel}>UF</span>
            <select
              value={draftUf}
              disabled={disabled}
              onChange={(e) => setDraftUf(e.target.value)}
              className={cn(budgetSelect, "min-w-[72px]")}
            >
              {(draftSource === "cicro" ? cicroUfOptions : BRAZIL_UFS).map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </label>

          <label className="min-w-[min(100%,220px)] flex-1 text-sm text-slate-400">
            <span className={fieldLabel}>Período / versão</span>
            <select
              value={draftReference}
              disabled={disabled || draftRefs.length === 0}
              onChange={(e) => setDraftReference(e.target.value)}
              className={cn(budgetSelect, "w-full min-w-[180px]")}
            >
              {draftRefs.length === 0 ? (
                <option value="">Nenhum período importado</option>
              ) : (
                draftRefs.map((r) => (
                  <option key={r.reference} value={r.reference}>
                    {r.label ?? referenceLabelFromKey(r.reference)}
                  </option>
                ))
              )}
            </select>
          </label>

          <div className="flex flex-wrap gap-2">
            {editingSource ? (
              <>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={handleSaveEdit}
                  className={cn(budgetBtn, "bg-cyan-600/25 text-cyan-200 ring-cyan-500/40 hover:bg-cyan-600/35")}
                >
                  Salvar
                </button>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => resetDraft()}
                  className={cn(budgetBtn, "text-slate-400 ring-slate-600 hover:bg-slate-800/60")}
                >
                  Cancelar
                </button>
              </>
            ) : (
              <button
                type="button"
                disabled={disabled || !draftReference}
                onClick={handleAdd}
                className={cn(budgetBtn, "bg-emerald-600/25 text-emerald-200 ring-emerald-500/40 hover:bg-emerald-600/35")}
              >
                Adicionar base
              </button>
            )}
          </div>
        </div>
        {formError && <p className="mt-2 text-xs text-amber-300">{formError}</p>}
      </div>

      <div className="px-5 py-4">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Bases neste orçamento ({activeBases.length})
        </p>
        <div className="mt-3 overflow-hidden rounded-lg bg-slate-950/50 ring-1 ring-slate-800/80">
          {activeBases.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-slate-500">
              Nenhuma base adicionada. Use o formulário acima e clique em Adicionar base.
            </p>
          ) : (
            <ul className="divide-y divide-slate-800/80">
              {activeBases.map((row) => (
                <li
                  key={row.source}
                  className={cn(
                    "flex flex-wrap items-center justify-between gap-3 px-4 py-3",
                    editingSource === row.source && "bg-cyan-500/5"
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-200">{row.label}</p>
                    <p className="text-xs text-slate-500">
                      UF {row.uf} · {refLabel(row, references)}
                    </p>
                    <p className="mt-0.5 font-mono text-[10px] text-slate-600">{row.reference}</p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => handleStartEdit(row)}
                      className={cn(
                        budgetBtn,
                        "px-3 py-1 text-xs text-cyan-300 ring-cyan-500/30 hover:bg-cyan-500/10"
                      )}
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => handleRemove(row.source)}
                      className={cn(
                        budgetBtn,
                        "px-3 py-1 text-xs text-red-300 ring-red-500/30 hover:bg-red-500/10"
                      )}
                    >
                      Remover
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
