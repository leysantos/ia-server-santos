"use client";

import { budgetBtn } from "@/lib/budget-ui";
import { cn } from "@/lib/utils";

interface BudgetAnalyticsExportActionsProps {
  docKey: "curva_abc" | "curva_s" | "histograma";
  label: string;
  disabled?: boolean;
  onExportPdf?: (docKey: string, label: string) => void;
  onExportExcel?: (docKey: string, label: string) => void;
  className?: string;
}

export default function BudgetAnalyticsExportActions({
  docKey,
  label,
  disabled,
  onExportPdf,
  onExportExcel,
  className,
}: BudgetAnalyticsExportActionsProps) {
  if (!onExportPdf && !onExportExcel) return null;

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {onExportPdf && (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onExportPdf(docKey, label)}
          className={cn(
            budgetBtn,
            "bg-rose-600/20 px-3 py-1.5 text-xs text-rose-200 ring-rose-500/40 hover:bg-rose-600/30"
          )}
        >
          PDF
        </button>
      )}
      {onExportExcel && (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onExportExcel(docKey, label)}
          className={cn(
            budgetBtn,
            "bg-emerald-600/20 px-3 py-1.5 text-xs text-emerald-300 ring-emerald-500/40 hover:bg-emerald-600/30"
          )}
        >
          Excel
        </button>
      )}
    </div>
  );
}
