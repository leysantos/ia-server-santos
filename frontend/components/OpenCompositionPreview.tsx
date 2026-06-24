"use client";

import type { OpenCompositionDetail } from "@/types/api";
import {
  formatBrl,
  formatLaborChargePct,
  formatPctAs,
  previewPctAs,
  previewTotalSemd,
} from "@/lib/open-composition-ui";
import OpenCompositionItemsTable from "@/components/OpenCompositionItemsTable";
import { cn } from "@/lib/utils";
import { referenceLabelFromKey } from "@/lib/brazil-ufs";

interface OpenCompositionPreviewProps {
  preview: OpenCompositionDetail;
  priceMode: "comd" | "semd";
  referenceLabel?: string;
  className?: string;
}

export default function OpenCompositionPreview({
  preview,
  priceMode,
  referenceLabel,
  className,
}: OpenCompositionPreviewProps) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <p className="mb-2 text-sm text-slate-300">
        <strong>{preview.code}</strong> — {preview.description} ({preview.unit})
        {preview.grupo ? (
          <span className="ml-2 text-xs text-slate-500">· Grupo: {preview.grupo}</span>
        ) : null}
      </p>
      <div className="mb-3 flex flex-wrap gap-4 text-sm">
        <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-emerald-200 ring-1 ring-emerald-500/30">
          ComD (CCD): <strong className="tabular-nums">{formatBrl(preview.total_price)}</strong>
        </span>
        <span className="rounded-lg bg-cyan-500/10 px-3 py-1.5 text-cyan-200 ring-1 ring-cyan-500/30">
          SemD (CSD):{" "}
          <strong className="tabular-nums">{formatBrl(previewTotalSemd(preview))}</strong>
        </span>
        {(preview.pct_as_comd != null || preview.pct_as_semd != null) && (
          <span
            className="rounded-lg bg-amber-500/10 px-3 py-1.5 text-amber-200 ring-1 ring-amber-500/30"
            title="% do custo obtido com preços de insumos de São Paulo por indisponibilidade no estado"
          >
            %AS: <strong className="tabular-nums">{formatPctAs(previewPctAs(preview, priceMode))}</strong>
            {preview.tp2 === "AS" ? " · tp2 AS" : ""}
          </span>
        )}
        {preview.tp2 === "AS" && preview.pct_as_comd == null && preview.pct_as_semd == null && (
          <span className="rounded-lg bg-amber-500/10 px-3 py-1.5 text-amber-200 ring-1 ring-amber-500/30">
            tp2: <strong>AS</strong>
          </span>
        )}
        {preview.labor_charges &&
          (preview.labor_charges.horista_comd || preview.labor_charges.horista_semd) && (
            <span className="rounded-lg bg-violet-500/10 px-3 py-1.5 text-violet-200 ring-1 ring-violet-500/30">
              Horista:{" "}
              <strong className="tabular-nums">
                {formatLaborChargePct(
                  priceMode === "semd"
                    ? preview.labor_charges.horista_semd
                    : preview.labor_charges.horista_comd
                )}
              </strong>
              {" · "}
              Mensalista:{" "}
              <strong className="tabular-nums">
                {formatLaborChargePct(
                  priceMode === "semd"
                    ? preview.labor_charges.mensalista_semd
                    : preview.labor_charges.mensalista_comd
                )}
              </strong>
            </span>
          )}
        {(preview.price_uf || referenceLabel) && (
          <span className="self-center text-xs text-slate-500">
            {preview.price_uf ? `UF ${preview.price_uf}` : ""}
            {referenceLabel ? ` · ${referenceLabel}` : ""}
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
      <OpenCompositionItemsTable items={preview.items} priceMode={priceMode} />
    </div>
  );
}

export function refLabelFromReference(reference: string, label?: string): string {
  return label ?? referenceLabelFromKey(reference);
}
