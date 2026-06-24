"use client";

import BudgetPriceBasesPanel from "@/components/BudgetPriceBasesPanel";
import BudgetProjectForm, { type ProjectFormValues } from "@/components/BudgetProjectForm";
import type { BdiObraType, BudgetPriceBaseSelection, BudgetProjectInfo, BudgetSummary } from "@/types/api";
import { useMemo } from "react";

interface BudgetDadosTabProps {
  project?: BudgetProjectInfo;
  bdiTypes: BdiObraType[];
  priceBases: BudgetPriceBaseSelection[];
  savedItems?: BudgetSummary[];
  disabled?: boolean;
  sinapiImported: boolean;
  onProjectChange: (values: ProjectFormValues) => void;
  onObraTypeChange: (type: string) => void;
  onPriceBasesChange: (next: BudgetPriceBaseSelection[]) => void;
}

export default function BudgetDadosTab({
  project,
  bdiTypes,
  priceBases,
  savedItems = [],
  disabled,
  sinapiImported,
  onProjectChange,
  onObraTypeChange,
  onPriceBasesChange,
}: BudgetDadosTabProps) {
  const existingOrcCodes = useMemo(() => {
    const codes = savedItems.map((s) => s.orcamento).filter(Boolean) as string[];
    if (project?.orcamento) codes.push(project.orcamento);
    return codes;
  }, [savedItems, project?.orcamento]);

  return (
    <div className="space-y-4">
      {!sinapiImported && (
        <div className="rounded-xl bg-amber-500/10 px-4 py-3 text-sm text-amber-200 ring-1 ring-amber-500/30">
          Importe ao menos um período em{" "}
          <a href="/settings/price-bases" className="text-cyan-300 underline">
            Configurações → Bases de preços
          </a>{" "}
          antes de compor serviços nas etapas.
        </div>
      )}

      <BudgetProjectForm
        project={project}
        bdiTypes={bdiTypes}
        disabled={disabled}
        existingOrcCodes={existingOrcCodes}
        onChange={onProjectChange}
        onObraTypeChange={onObraTypeChange}
      />

      <BudgetPriceBasesPanel
        value={priceBases}
        disabled={disabled}
        onChange={onPriceBasesChange}
      />
    </div>
  );
}
