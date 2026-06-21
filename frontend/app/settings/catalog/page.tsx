"use client";

import DocumentLibrary from "@/components/DocumentLibrary";
import { useSettingsKnowledge } from "@/contexts/SettingsKnowledgeContext";

export default function SettingsCatalogPage() {
  const {
    options,
    stats,
    catalog,
    refresh,
    handleActivatePriceBase,
    handleIndexBudgetModel,
    handleUpdateDocument,
    handleDeleteDocument,
  } = useSettingsKnowledge();

  if (!options) return null;

  return (
    <DocumentLibrary
      view="catalog"
      options={options}
      stats={stats}
      catalog={catalog?.items ?? []}
      onActivatePriceBase={handleActivatePriceBase}
      onIndexBudgetModel={handleIndexBudgetModel}
      onUpdateDocument={handleUpdateDocument}
      onDeleteDocument={handleDeleteDocument}
      onRefresh={refresh}
    />
  );
}
