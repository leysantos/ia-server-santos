"use client";

import DocumentLibrary from "@/components/DocumentLibrary";
import NormBulkImport from "@/components/NormBulkImport";
import { useSettingsKnowledge } from "@/contexts/SettingsKnowledgeContext";
import { api } from "@/services/api";

export default function SettingsImportsPage() {
  const { options, refresh } = useSettingsKnowledge();

  if (!options) return null;

  return (
    <div className="space-y-6">
      <NormBulkImport />
      <DocumentLibrary
      view="import"
      options={options}
      catalog={[]}
      onIngest={(formData) => api.knowledgeIngest(formData)}
      onRefresh={refresh}
    />
    </div>
  );
}
