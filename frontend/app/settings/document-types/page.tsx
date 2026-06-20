"use client";

import DocumentTypePresetsPanel from "@/components/DocumentTypePresetsPanel";
import { useSettingsKnowledge } from "@/contexts/SettingsKnowledgeContext";
import { api } from "@/services/api";

export default function SettingsDocumentTypesPage() {
  const { options, refresh } = useSettingsKnowledge();

  if (!options) return null;

  return (
    <DocumentTypePresetsPanel
      embedded
      options={options}
      onCreate={(body) => api.knowledgeCreateDocumentTypePreset(body)}
      onUpdate={(id, body) => api.knowledgeUpdateDocumentTypePreset(id, body)}
      onDelete={(id) => api.knowledgeDeleteDocumentTypePreset(id)}
      onRefresh={refresh}
    />
  );
}
