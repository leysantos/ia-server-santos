"use client";

import DocumentLibrary from "@/components/DocumentLibrary";
import { useSettingsKnowledge } from "@/contexts/SettingsKnowledgeContext";
import { api, knowledgeIngestWebWithProgress } from "@/services/api";

export default function SettingsImportsPage() {
  const { options, refresh } = useSettingsKnowledge();

  if (!options) return null;

  return (
    <div className="space-y-6">
      <DocumentLibrary
      view="import"
      options={options}
      catalog={[]}
      onIngest={(formData) => api.knowledgeIngest(formData)}
      onIngestWeb={(body, onProgress) =>
        knowledgeIngestWebWithProgress(
          { ...body, auto_index: true },
          onProgress ?? (() => {})
        )
      }
      onRefresh={refresh}
    />
    </div>
  );
}
