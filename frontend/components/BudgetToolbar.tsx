"use client";

import { useRef } from "react";
import { cn } from "@/lib/utils";
import { budgetBtn } from "@/lib/budget-ui";

interface BudgetToolbarProps {
  hasSession: boolean;
  loading: boolean;
  onNew: () => void;
  onImportTemplate: (file: File) => void;
  onSave?: () => void;
  onExport?: () => void;
  onRenumber?: () => void;
}

export default function BudgetToolbar({
  hasSession,
  loading,
  onNew,
  onImportTemplate,
  onSave,
  onExport,
  onRenumber,
}: BudgetToolbarProps) {
  const templateRef = useRef<HTMLInputElement>(null);

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

      <button
        type="button"
        disabled={loading}
        onClick={() => templateRef.current?.click()}
        className={cn(budgetBtn, "bg-violet-600/20 px-4 text-sm text-violet-300 ring-violet-500/40 hover:bg-violet-600/30")}
      >
        Importar template de modelo
      </button>
      <input
        ref={templateRef}
        type="file"
        accept=".xlsm,.xlsx,.xls"
        className="hidden"
        disabled={loading}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onImportTemplate(f);
          if (templateRef.current) templateRef.current.value = "";
        }}
      />

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

      {hasSession && onExport && (
        <button
          type="button"
          onClick={onExport}
          className={cn(budgetBtn, "bg-emerald-600/20 px-4 text-sm text-emerald-300 ring-emerald-500/40 hover:bg-emerald-600/30")}
        >
          Gerar planilha Excel
        </button>
      )}
    </div>
  );
}
