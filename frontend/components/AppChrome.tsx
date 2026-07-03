"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import WorkspacePanelLoader from "@/components/WorkspacePanelLoader";
import ActivityPanel from "@/components/ActivityPanel";
import ChatStreamBanner from "@/components/ChatStreamBanner";
import VisionJobBanner from "@/components/VisionJobBanner";
import NormBulkImportBanner from "@/components/NormBulkImportBanner";
import KnowledgeWebImportBanner from "@/components/KnowledgeWebImportBanner";
import MobileBottomNav from "@/components/mobile/MobileBottomNav";
import { ModelsStatusProvider } from "@/components/ModelsStatusBadge";
import { WorkspaceShellProvider } from "@/components/WorkspaceShellContext";
import { ActivityProvider } from "@/context/ActivityContext";
import { ChatStreamProvider } from "@/context/ChatStreamContext";
import { NormBulkImportProvider } from "@/context/NormBulkImportContext";
import { KnowledgeWebImportProvider } from "@/context/KnowledgeWebImportContext";
import { VisionJobProvider } from "@/context/VisionJobContext";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { loading, authEnabled, user } = useAuth();
  const isLogin = pathname === "/login" || pathname.startsWith("/login/");

  if (isLogin) {
    return <>{children}</>;
  }

  if (authEnabled && (loading || !user)) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-surface text-slate-400">
        <div className="text-sm">Verificando autenticação…</div>
      </div>
    );
  }

  return (
    <WorkspaceShellProvider>
      <ModelsStatusProvider>
        <ActivityProvider>
          <ChatStreamProvider>
            <VisionJobProvider>
              <NormBulkImportProvider>
                <KnowledgeWebImportProvider>
                  <div className="flex h-dvh overflow-hidden">
                    <Sidebar />
                    <WorkspacePanelLoader />
                    <main
                      className={cn(
                        "app-ambient relative flex min-w-0 flex-1 flex-col overflow-hidden bg-surface",
                        "pb-[calc(3.75rem+env(safe-area-inset-bottom,0px))] lg:pb-0"
                      )}
                    >
                      <ChatStreamBanner />
                      <VisionJobBanner />
                      <NormBulkImportBanner />
                      <KnowledgeWebImportBanner />
                      {children}
                    </main>
                    <ActivityPanel />
                  </div>
                  <MobileBottomNav />
                </KnowledgeWebImportProvider>
              </NormBulkImportProvider>
            </VisionJobProvider>
          </ChatStreamProvider>
        </ActivityProvider>
      </ModelsStatusProvider>
    </WorkspaceShellProvider>
  );
}

export default function AppChrome({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
