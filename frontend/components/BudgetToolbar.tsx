"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { budgetBtn, budgetSelect } from "@/lib/budget-ui";

export const EXPORT_DOCS = [
  { key: "orc_sintetico", label: "Orç. Sintético" },
  { key: "orc_analitico", label: "Orç. Analítico" },
  { key: "mcq", label: "MCQ" },
  { key: "cronograma", label: "Cronograma" },
  { key: "curva_abc", label: "Curva ABC" },
  { key: "curva_s", label: "Curva S" },
  { key: "histograma", label: "Histograma" },
  { key: "esp_tecnica", label: "Esp. Técnica" },
] as const;

/** @deprecated use EXPORT_DOCS */
export const EXPORT_PDF_DOCS = EXPORT_DOCS;

interface BudgetToolbarProps {
  hasSession: boolean;
  loading: boolean;
  onNew: () => void;
  onSave?: () => void;
  onExportExcel?: (docKey: string, label: string) => void;
  onExportPdf?: (docKey: string, label: string) => void;
  onRenumber?: () => void;
}

export default function BudgetToolbar({
  hasSession,
  loading,
  onNew,
  onSave,
  onExportExcel,
  onExportPdf,
  onRenumber,
}: BudgetToolbarProps) {
  const [exportDocKey, setExportDocKey] = useState<string>(EXPORT_DOCS[0].key);

  const selectedDoc = () => EXPORT_DOCS.find((d) => d.key === exportDocKey);

  const handleGeneratePdf = () => {
    if (!onExportPdf) return;
    const doc = selectedDoc();
    if (doc) onExportPdf(doc.key, doc.label);
  };

  const handleDownloadExcel = () => {
    if (!onExportExcel) return;
    const doc = selectedDoc();
    if (doc) onExportExcel(doc.key, doc.label);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        disabled={loading}
        onClick={onNew}
        className={cn(budgetBtn, "bg-cyan-600/20 px-4 text-sm text-cyan-300 ring-cyan-500/40 hover:bg-cyan-600/30")}
      >
        Novo orçamento
      </button>

      {onSave && (
        <button
          type="button"
          disabled={loading || !hasSession}
          onClick={onSave}
          className={cn(budgetBtn, "bg-indigo-600/20 px-4 text-sm text-indigo-300 ring-indigo-500/40 hover:bg-indigo-600/30")}
        >
          Salvar
        </button>
      )}

      {hasSession && onRenumber && (
        <button
          type="button"
          disabled={loading}
          onClick={onRenumber}
          className={cn(budgetBtn, "bg-amber-600/20 px-4 text-sm text-amber-300 ring-amber-500/40 hover:bg-amber-600/30")}
        >
          Organizar numeração
        </button>
      )}

      {hasSession && (onExportPdf || onExportExcel) && (
        <div className="flex items-center gap-2">
          <select
            value={exportDocKey}
            onChange={(e) => setExportDocKey(e.target.value)}
            disabled={loading}
            aria-label="Tipo de documento"
            className={cn(budgetSelect, "w-auto min-w-[11.5rem]")}
          >
            {EXPORT_DOCS.map((doc) => (
              <option key={doc.key} value={doc.key}>
                {doc.label}
              </option>
            ))}
          </select>
          {onExportPdf && (
            <button
              type="button"
              disabled={loading}
              onClick={handleGeneratePdf}
              className={cn(
                budgetBtn,
                "bg-rose-600/20 px-4 text-sm text-rose-200 ring-rose-500/40 hover:bg-rose-600/30"
              )}
            >
              Gerar PDF
            </button>
          )}
          {onExportExcel && (
            <button
              type="button"
              disabled={loading}
              onClick={handleDownloadExcel}
              className={cn(
                budgetBtn,
                "bg-emerald-600/20 px-4 text-sm text-emerald-300 ring-emerald-500/40 hover:bg-emerald-600/30"
              )}
            >
              Baixar Excel
            </button>
          )}
        </div>
      )}
    </div>
  );
}
