import type { Metadata } from "next";
import localFont from "next/font/local";
import Sidebar from "@/components/Sidebar";
import WorkspacePanelLoader from "@/components/WorkspacePanelLoader";
import ActivityPanel from "@/components/ActivityPanel";
import ChatStreamBanner from "@/components/ChatStreamBanner";
import VisionJobBanner from "@/components/VisionJobBanner";
import NormBulkImportBanner from "@/components/NormBulkImportBanner";
import KnowledgeWebImportBanner from "@/components/KnowledgeWebImportBanner";
import { ModelsStatusProvider } from "@/components/ModelsStatusBadge";
import { WorkspaceShellProvider } from "@/components/WorkspaceShellContext";
import { ActivityProvider } from "@/context/ActivityContext";
import { ChatStreamProvider } from "@/context/ChatStreamContext";
import { NormBulkImportProvider } from "@/context/NormBulkImportContext";
import { KnowledgeWebImportProvider } from "@/context/KnowledgeWebImportContext";
import { VisionJobProvider } from "@/context/VisionJobContext";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "IA Server Santos",
  description: "SaaS de engenharia multidisciplinar com IA e RAG v2",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className={`${geistSans.variable} min-h-screen bg-surface font-sans antialiased`}>
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
                    <main className="app-ambient relative flex min-w-0 flex-1 flex-col overflow-hidden bg-surface">
                      <ChatStreamBanner />
                      <VisionJobBanner />
                      <NormBulkImportBanner />
                      <KnowledgeWebImportBanner />
                      {children}
                    </main>
                    <ActivityPanel />
                  </div>
                  </KnowledgeWebImportProvider>
                </NormBulkImportProvider>
              </VisionJobProvider>
              </ChatStreamProvider>
            </ActivityProvider>
          </ModelsStatusProvider>
        </WorkspaceShellProvider>
      </body>
    </html>
  );
}
