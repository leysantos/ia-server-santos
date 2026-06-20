"use client";

import type { ReactNode } from "react";
import SettingsShell from "@/components/settings/SettingsShell";
import { SettingsKnowledgeProvider } from "@/contexts/SettingsKnowledgeContext";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <SettingsKnowledgeProvider>
      <SettingsShell>{children}</SettingsShell>
    </SettingsKnowledgeProvider>
  );
}
