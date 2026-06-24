"use client";

import type { OpenCompositionItem } from "@/types/api";
import { cpuItemTypeLabel } from "@/lib/open-composition-ui";
import { cn } from "@/lib/utils";

interface OpenCompositionItemsTableProps {
  items: OpenCompositionItem[];
  priceMode: "comd" | "semd";
  className?: string;
  compact?: boolean;
}

export default function OpenCompositionItemsTable({
  items,
  priceMode,
  className,
  compact = false,
}: OpenCompositionItemsTableProps) {
  if (items.length === 0) {
    return (
      <p className="px-3 py-4 text-xs text-amber-400/90">
        Composição sem detalhamento analítico nesta base.
      </p>
    );
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-left text-xs text-slate-400">
        <thead>
          <tr className="border-b border-slate-700/80 text-slate-500">
            <th className="px-3 py-2">Tipo</th>
            {!compact && <th className="px-3 py-2">Classif.</th>}
            <th className="px-3 py-2">Código</th>
            <th className="px-3 py-2">Descrição</th>
            <th className="px-3 py-2">Und</th>
            <th className="px-3 py-2 text-right">Coef.</th>
            {!compact && <th className="px-3 py-2">Origem</th>}
            <th className="px-3 py-2">tp2</th>
            <th className="px-3 py-2 text-right">
              Preço un. {priceMode === "comd" ? "(ComD)" : "(SemD)"}
            </th>
            <th className="px-3 py-2 text-right">
              Parcial {priceMode === "comd" ? "(ComD)" : "(SemD)"}
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => {
            const unitPrice =
              priceMode === "semd" ? item.unit_price_sem ?? item.unit_price : item.unit_price;
            const partialCost =
              priceMode === "semd" ? item.partial_cost_sem ?? item.partial_cost : item.partial_cost;
            return (
              <tr key={`${item.code}-${i}`} className="border-b border-slate-800/60">
                <td className="px-3 py-1.5 text-cyan-400/90">{cpuItemTypeLabel(item.item_type)}</td>
                {!compact && <td className="px-3 py-1.5">{item.classificacao || "—"}</td>}
                <td className="px-3 py-1.5 font-mono text-slate-300">{item.code}</td>
                <td className="max-w-[min(100%,280px)] truncate px-3 py-1.5" title={item.description}>
                  {item.description}
                </td>
                <td className="px-3 py-1.5">{item.unit}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{item.coefficient}</td>
                {!compact && (
                  <td className="px-3 py-1.5 font-mono text-slate-500">{item.origem_preco || "—"}</td>
                )}
                <td
                  className={cn(
                    "px-3 py-1.5 font-mono",
                    item.tp2 === "AS" ? "text-amber-300" : "text-slate-600"
                  )}
                >
                  {item.tp2 || "—"}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums">
                  {unitPrice.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums">
                  {partialCost.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
