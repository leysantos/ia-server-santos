"use client";

import { useEffect, useState } from "react";
import BudgetHistoryLeftPanel from "@/components/BudgetHistoryLeftPanel";
import BudgetSavedPanel from "@/components/BudgetSavedPanel";
import { api } from "@/services/api";
import type { BudgetSessionResponse, BudgetSummary } from "@/types/api";

interface BudgetHistoricoTabProps {
  savedItems: BudgetSummary[];
  activeId?: string | null;
  projectFilterLabel?: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  onClearProjectFilter?: () => void;
}

export default function BudgetHistoricoTab({
  savedItems,
  activeId,
  projectFilterLabel,
  onOpen,
  onDelete,
  onNew,
  onClearProjectFilter,
}: BudgetHistoricoTabProps) {
  const [selectedId, setSelectedId] = useState<string | null>(activeId ?? null);
  const [preview, setPreview] = useState<BudgetSessionResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!activeId) return;
    if (savedItems.some((item) => item.id === activeId)) {
      setSelectedId(activeId);
    } else if (savedItems.length > 0) {
      setSelectedId(null);
      setPreview(null);
    }
  }, [activeId, savedItems]);

  useEffect(() => {
    if (!selectedId || !savedItems.some((item) => item.id === selectedId)) {
      setPreview(null);
      setPreviewLoading(false);
      return;
    }
    let cancelled = false;
    setPreviewLoading(true);
    void api
      .pricingGetSaved(selectedId)
      .then((data) => {
        if (!cancelled) setPreview(data);
      })
      .catch(() => {
        if (!cancelled) setPreview(null);
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, savedItems]);

  const handleDelete = (id: string) => {
    if (selectedId === id) {
      setSelectedId(null);
      setPreview(null);
    }
    onDelete(id);
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <BudgetHistoryLeftPanel
        items={savedItems}
        selectedId={selectedId}
        preview={preview}
        previewLoading={previewLoading}
      />
      <BudgetSavedPanel
        items={savedItems}
        selectedId={selectedId}
        activeId={activeId}
        projectFilterLabel={projectFilterLabel}
        onSelect={setSelectedId}
        onOpen={onOpen}
        onDelete={handleDelete}
        onNew={onNew}
        onClearProjectFilter={onClearProjectFilter}
        layout="full"
      />
    </div>
  );
}
