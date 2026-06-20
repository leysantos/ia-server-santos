"use client";

import { useCallback, useState } from "react";
import type { BudgetRow, BudgetSessionResponse } from "@/types/api";
import { cn } from "@/lib/utils";
import {
  bdiComdLabel,
  bdiSemdLabel,
  modeColorClass,
  rowDualTotals,
} from "@/lib/budget-desoneracao";
import { BudgetSpreadsheetFooterRows } from "@/components/BudgetTotalsSummary";

interface BudgetSpreadsheetProps {
  session: BudgetSessionResponse;
  onUpdate: (session: BudgetSessionResponse) => void;
  onCellEdit?: (
    rowId: string,
    field: string,
    value: number | string,
    code?: string
  ) => Promise<BudgetSessionResponse>;
}

function fmt(n: number | undefined) {
  if (n == null || n === 0) return "—";
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function BudgetSpreadsheet({
  session,
  onUpdate,
  onCellEdit,
}: BudgetSpreadsheetProps) {
  const [editing, setEditing] = useState<{ rowId: string; field: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const comdHeader = bdiComdLabel(session);
  const semdHeader = bdiSemdLabel(session);

  const handleBlur = useCallback(
    async (row: BudgetRow, field: string, raw: string) => {
      setEditing(null);
      if (!onCellEdit || !row.editable) return;

      let current: string | number = row.name;
      if (field === "quantity") current = row.quantity;
      if (field === "unit_cost") current = row.unit_cost;
      if (field === "unit_price") current = row.unit_price;

      const value = field === "name" ? raw : parseFloat(raw.replace(",", "."));
      if (value === current || (field !== "name" && Number.isNaN(value as number))) return;

      setSaving(true);
      try {
        const updated = await onCellEdit(row.row_id, field, value, row.code);
        onUpdate(updated);
      } finally {
        setSaving(false);
      }
    },
    [onCellEdit, onUpdate]
  );

  const renderEditable = (row: BudgetRow, field: "quantity" | "unit_cost" | "name", align = "right") => {
    const val = field === "name" ? row.name : field === "quantity" ? row.quantity : row.unit_cost;
    if (editing?.rowId === row.row_id && editing.field === field) {
      if (field === "name") {
        return (
          <textarea
            autoFocus
            defaultValue={val}
            rows={Math.min(6, Math.max(2, String(val).split("\n").length + 1))}
            className="w-full min-w-[200px] rounded bg-slate-800 px-2 py-1 text-sm ring-1 ring-cyan-500/50 whitespace-pre-wrap"
            onBlur={(e) => handleBlur(row, field, e.target.value)}
          />
        );
      }
      return (
        <input
          autoFocus
          defaultValue={val}
          className={cn(
            "rounded bg-slate-800 px-2 py-1 text-sm ring-1 ring-cyan-500/50",
            align === "right" ? "w-24 text-right" : "w-full"
          )}
          onBlur={(e) => handleBlur(row, field, e.target.value)}
        />
      );
    }
    return (
      <span
        className={cn(
          row.editable && "cursor-text hover:text-cyan-300",
          align === "right" && "tabular-nums",
          field === "name" && "block whitespace-pre-wrap break-words leading-snug"
        )}
        onClick={() => row.editable && setEditing({ rowId: row.row_id, field })}
      >
        {field === "name" ? row.name : field === "quantity" ? row.quantity || "—" : fmt(row.unit_cost)}
      </span>
    );
  };

  return (
    <div className="overflow-hidden rounded-xl ring-1 ring-slate-700/80">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1200px] text-sm">
          <thead>
            <tr className="bg-slate-800/80 text-left text-xs uppercase tracking-wider text-slate-400">
              <th className="px-2 py-2.5">Item</th>
              <th className="px-2 py-2.5">Cód.</th>
              <th className="px-2 py-2.5">Descrição</th>
              <th className="px-2 py-2.5 text-right">Qtd</th>
              <th className="px-2 py-2.5">Un</th>
              <th className="px-2 py-2.5 text-right">Custo unit.</th>
              <th className="px-2 py-2.5 text-right">PU ComD</th>
              <th className="px-2 py-2.5 text-right">PU SemD</th>
              <th className="px-2 py-2.5 text-right">{comdHeader}</th>
              <th className="px-2 py-2.5 text-right">{semdHeader}</th>
              <th className="px-2 py-2.5">Base</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {session.rows.map((row) => {
              if (row.is_memory_row) {
                return (
                  <tr key={row.row_id} className="bg-slate-900/20 italic text-slate-500">
                    <td colSpan={11} className="px-3 py-1.5 text-xs" style={{ paddingLeft: `${24 + row.level * 16}px` }}>
                      ↳ {row.calculation_note || row.name}
                    </td>
                  </tr>
                );
              }
              const isEtapa = row.row_type === "ETAPA" || row.level === 0;
              const { comd, semd } = rowDualTotals(row);
              return (
                <tr
                  key={row.row_id}
                  className={cn(
                    "hover:bg-slate-800/30",
                    isEtapa ? "bg-slate-800/50 font-semibold text-slate-100" : "bg-slate-900/40"
                  )}
                >
                  <td className="px-2 py-2 font-mono text-xs text-slate-500">{row.code}</td>
                  <td className="px-2 py-2 font-mono text-xs text-slate-500">{row.source_code || "—"}</td>
                  <td className="px-2 py-2 text-slate-200 min-w-[14rem] max-w-lg" style={{ paddingLeft: `${8 + row.level * 14}px` }}>
                    {row.row_type === "S" && !isEtapa ? (
                      renderEditable(row, "name", "left")
                    ) : (
                      <span className="block whitespace-pre-wrap break-words leading-snug">{row.name}</span>
                    )}
                  </td>
                  <td className="px-2 py-2 text-right text-slate-300">{renderEditable(row, "quantity")}</td>
                  <td className="px-2 py-2 text-slate-500">{row.unit || "—"}</td>
                  <td className="px-2 py-2 text-right text-slate-300">
                    {row.row_type === "S" && !isEtapa ? renderEditable(row, "unit_cost") : "—"}
                  </td>
                  <td className={cn("px-2 py-2 text-right", modeColorClass("comd"))}>
                    {fmt(row.unit_price)}
                  </td>
                  <td className={cn("px-2 py-2 text-right", modeColorClass("semd"))}>
                    {fmt(row.unit_price_semd)}
                  </td>
                  <td className={cn("px-2 py-2 text-right", modeColorClass("comd", isEtapa))}>
                    {fmt(comd)}
                  </td>
                  <td className={cn("px-2 py-2 text-right", modeColorClass("semd", isEtapa))}>
                    {fmt(semd)}
                  </td>
                  <td className="px-2 py-2 text-xs text-slate-500">{row.source_base}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <BudgetSpreadsheetFooterRows session={session} colSpan={8} />
          </tfoot>
        </table>
      </div>
      {saving && (
        <div className="border-t border-slate-800/80 px-3 py-1.5 text-xs text-cyan-400">
          Recalculando BDI e totais…
        </div>
      )}
    </div>
  );
}
