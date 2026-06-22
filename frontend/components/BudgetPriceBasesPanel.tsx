"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BudgetPriceBaseSelection, PriceBankReference } from "@/types/api";
import { BRAZIL_UFS, referenceLabelFromKey } from "@/lib/brazil-ufs";
import { cn } from "@/lib/utils";
import { budgetSelect } from "@/lib/budget-ui";

const CATALOG_BASES: Array<{
  source: string;
  label: string;
  category: string;
  available: boolean;
  hint?: string;
}> = [
  { source: "sinapi", label: "SINAPI", category: "Bases nacionais", available: true },
  { source: "sbc", label: "SBC", category: "Bases nacionais", available: false, hint: "Em breve" },
  { source: "cicro", label: "SICRO3", category: "Bases nacionais", available: false, hint: "Em breve" },
  { source: "tcpo", label: "TCPO", category: "Bases regionais", available: false, hint: "Em breve" },
  { source: "orse", label: "ORSE", category: "Bases regionais", available: false, hint: "Em breve" },
];

function defaultSelection(
  source: string,
  label: string,
  references: PriceBankReference[],
  uf = "SP"
): BudgetPriceBaseSelection {
  const ref = references[0]?.reference ?? "";
  return {
    source,
    label,
    enabled: source === "sinapi",
    uf,
    reference: ref,
  };
}

interface BudgetPriceBasesPanelProps {
  value: BudgetPriceBaseSelection[];
  disabled?: boolean;
  onChange: (next: BudgetPriceBaseSelection[]) => void;
}

export default function BudgetPriceBasesPanel({ value, disabled, onChange }: BudgetPriceBasesPanelProps) {
  const [references, setReferences] = useState<PriceBankReference[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api
      .pricingSyncBankReferences()
      .then((res) => setReferences(res.references ?? []))
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Falha ao carregar períodos"));
  }, []);

  const merged = useMemo(() => {
    const bySource = new Map(value.map((v) => [v.source, v]));
    return CATALOG_BASES.map((base) => {
      const existing = bySource.get(base.source);
      if (existing) return { ...base, ...existing };
      return { ...defaultSelection(base.source, base.label, references), ...base };
    });
  }, [value, references]);

  const patchRow = useCallback(
    (source: string, patch: Partial<BudgetPriceBaseSelection>) => {
      const next = merged.map((row) =>
        row.source === source ? { ...row, ...patch, source, label: row.label } : row
      );
      onChange(
        next.map(({ source: s, label, enabled, uf, reference }) => ({
          source: s,
          label,
          enabled,
          uf,
          reference,
        }))
      );
    },
    [merged, onChange]
  );

  const grouped = useMemo(() => {
    const map = new Map<string, typeof merged>();
    for (const row of merged) {
      const list = map.get(row.category) ?? [];
      list.push(row);
      map.set(row.category, list);
    }
    return [...map.entries()];
  }, [merged]);

  const sinapiImported = references.length > 0;

  return (
    <div className="overflow-hidden rounded-xl bg-slate-800/30 ring-1 ring-slate-700/50">
      <div className="border-b border-slate-700/60 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-200">Bases de preços do orçamento</h3>
        <p className="mt-1 text-xs text-slate-500">
          Selecione uma ou mais bases, o estado (UF) e o período de cada uma — como na composição do orçamento.
          Importe períodos em{" "}
          <a href="/settings/price-bases" className="text-cyan-400 underline">
            Configurações → Bases de preços
          </a>
          .
        </p>
        {loadError && <p className="mt-2 text-xs text-red-300">{loadError}</p>}
        {!sinapiImported && (
          <p className="mt-2 text-xs text-amber-300">
            Nenhum período SINAPI importado. Faça upload do ZIP nacional antes de compor serviços.
          </p>
        )}
      </div>

      {grouped.map(([category, rows]) => (
        <div key={category} className="border-b border-slate-800/80 last:border-b-0">
          <p className="bg-slate-900/40 px-4 py-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            {category}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="text-xs text-slate-500">
                  <th className="px-4 py-2 font-medium">Base</th>
                  <th className="px-4 py-2 font-medium">Local (UF)</th>
                  <th className="px-4 py-2 font-medium">Versão</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.source}
                    className={cn(
                      "border-t border-slate-800/60",
                      row.enabled && row.available && "bg-cyan-500/5"
                    )}
                  >
                    <td className="px-4 py-2.5">
                      <label className="flex items-center gap-2 text-slate-200">
                        <input
                          type="checkbox"
                          checked={row.enabled}
                          disabled={disabled || !row.available || (row.source === "sinapi" && !sinapiImported)}
                          onChange={(e) => patchRow(row.source, { enabled: e.target.checked })}
                          className="rounded border-slate-600 bg-slate-900 text-cyan-500"
                        />
                        <span>{row.label}</span>
                        {!row.available && (
                          <span className="text-xs text-slate-500">{row.hint ?? "Indisponível"}</span>
                        )}
                      </label>
                    </td>
                    <td className="px-4 py-2.5">
                      <select
                        value={row.uf}
                        disabled={disabled || !row.enabled || !row.available}
                        onChange={(e) => patchRow(row.source, { uf: e.target.value })}
                        className={cn(budgetSelect, "min-w-[7rem]")}
                      >
                        {BRAZIL_UFS.map((u) => (
                          <option key={u} value={u}>
                            {u}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-2.5">
                      {row.source === "sinapi" ? (
                        <select
                          value={row.reference}
                          disabled={disabled || !row.enabled || !sinapiImported}
                          onChange={(e) => patchRow(row.source, { reference: e.target.value })}
                          className={cn(budgetSelect, "min-w-[8rem]")}
                        >
                          {references.length === 0 ? (
                            <option value="">—</option>
                          ) : (
                            references.map((r) => (
                              <option key={r.reference} value={r.reference}>
                                {r.label ?? referenceLabelFromKey(r.reference)}
                              </option>
                            ))
                          )}
                        </select>
                      ) : (
                        <span className="text-xs text-slate-500">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
