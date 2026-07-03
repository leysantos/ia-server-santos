"use client";

import BudgetPriceBasesPanel from "@/components/BudgetPriceBasesPanel";
import BudgetBdiPanel from "@/components/BudgetBdiPanel";
import BudgetCommercialPanel, { type CommercialFormValues } from "@/components/BudgetCommercialPanel";
import BudgetCompliancePanel from "@/components/BudgetCompliancePanel";
import BudgetTenantSelector from "@/components/BudgetTenantSelector";
import BudgetPilotChecklist from "@/components/BudgetPilotChecklist";
import BudgetProjectForm, { type ProjectFormValues } from "@/components/BudgetProjectForm";
import type { BdiObraType, BudgetPriceBaseSelection, BudgetProjectInfo, BudgetSessionResponse, BudgetSummary } from "@/types/api";
import { useMemo } from "react";

interface BudgetDadosTabProps {
  sessionId: string;
  project?: BudgetProjectInfo;
  grandTotal?: number;
  bdiTypes: BdiObraType[];
  priceBases: BudgetPriceBaseSelection[];
  savedItems?: BudgetSummary[];
  disabled?: boolean;
  sinapiImported: boolean;
  onProjectChange: (values: ProjectFormValues) => void;
  onCommercialChange: (values: CommercialFormValues) => void;
  onComplianceDownload?: () => void;
  onObraTypeChange: (type: string) => void;
  onPriceBasesChange: (next: BudgetPriceBaseSelection[]) => void;
  onSessionUpdate: (session: BudgetSessionResponse) => void;
  onError?: (err: unknown, title?: string) => void;
}

export default function BudgetDadosTab({
  sessionId,
  project,
  grandTotal = 0,
  bdiTypes,
  priceBases,
  savedItems = [],
  disabled,
  sinapiImported,
  onProjectChange,
  onCommercialChange,
  onComplianceDownload,
  onObraTypeChange,
  onPriceBasesChange,
  onSessionUpdate,
  onError,
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

      <BudgetBdiPanel
        sessionId={sessionId}
        project={project}
        disabled={disabled}
        onUpdated={onSessionUpdate}
        onError={(err) => onError?.(err, "Falha ao aplicar BDI")}
      />

      <BudgetCommercialPanel
        project={project}
        grandTotal={grandTotal}
        disabled={disabled}
        onChange={onCommercialChange}
      />

      <BudgetTenantSelector />

      <BudgetCompliancePanel
        sessionId={sessionId}
        disabled={disabled}
        onDownload={onComplianceDownload}
        onError={onError}
      />

      <BudgetPriceBasesPanel
        value={priceBases}
        disabled={disabled}
        onChange={onPriceBasesChange}
      />

      <BudgetPilotChecklist sessionId={sessionId} />
    </div>
  );
}
