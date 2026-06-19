import type { Metadata } from "next";
import localFont from "next/font/local";
import Sidebar from "@/components/Sidebar";
import WorkspacePanelLoader from "@/components/WorkspacePanelLoader";
import { ModelsStatusProvider } from "@/components/ModelsStatusBadge";
import { WorkspaceShellProvider } from "@/components/WorkspaceShellContext";
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
      <body className={`${geistSans.variable} min-h-screen bg-slate-950 font-sans antialiased`}>
        <WorkspaceShellProvider>
          <ModelsStatusProvider>
            <div className="flex h-dvh overflow-hidden">
              <Sidebar />
              <WorkspacePanelLoader />
              <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
                {children}
              </main>
            </div>
          </ModelsStatusProvider>
        </WorkspaceShellProvider>
      </body>
    </html>
  );
}
