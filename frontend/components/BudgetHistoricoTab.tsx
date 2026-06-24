"use client";

import BudgetSavedPanel from "@/components/BudgetSavedPanel";
import BudgetTracePanel from "@/components/BudgetTracePanel";
import type { BudgetSummary } from "@/types/api";

interface BudgetHistoricoTabProps {
  savedItems: BudgetSummary[];
  activeId?: string | null;
  projectId?: string | null;
  projectFilterLabel?: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  onClearProjectFilter?: () => void;
}

export default function BudgetHistoricoTab({
  savedItems,
  activeId,
  projectId,
  projectFilterLabel,
  onOpen,
  onDelete,
  onNew,
  onClearProjectFilter,
}: BudgetHistoricoTabProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <BudgetTracePanel projectId={projectId} savedItems={savedItems} layout="full" />
      <BudgetSavedPanel
        items={savedItems}
        activeId={activeId}
        projectFilterLabel={projectFilterLabel}
        onOpen={onOpen}
        onDelete={onDelete}
        onNew={onNew}
        onClearProjectFilter={onClearProjectFilter}
        layout="full"
      />
    </div>
  );
}
