"use client";

import { Suspense, useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import WorkspacePanel from "@/components/WorkspacePanel";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useWorkspaceShell } from "@/components/WorkspaceShellContext";
import { useMobileLayout } from "@/hooks/useMobileLayout";
import { cn } from "@/lib/utils";

function WorkspacePanelShell() {
  const pathname = usePathname();
  const mobile = useMobileLayout();
  const { collapsed, hydrated, setCollapsed } = useWorkspaceShell();
  const showPanel = pathname === "/chat" || pathname.startsWith("/projects");

  const mobileInitRef = useRef(false);

  useEffect(() => {
    if (!mobile || !hydrated || mobileInitRef.current) return;
    mobileInitRef.current = true;
    setCollapsed(true);
  }, [mobile, hydrated, setCollapsed]);

  if (!showPanel) return null;

  if (mobile) {
    if (collapsed) return null;
    return (
      <>
        <button
          type="button"
          aria-label="Fechar painel"
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setCollapsed(true)}
        />
        <aside className="fixed inset-y-0 left-0 z-50 flex w-[min(100%,20rem)] flex-col border-r border-slate-800/80 bg-slate-950/98 shadow-xl lg:hidden">
          <WorkspacePanel onNavigate={() => setCollapsed(true)} />
        </aside>
      </>
    );
  }

  return (
    <div
      className={cn(
        "relative hidden h-full shrink-0 flex-col border-r border-slate-800/80 bg-slate-950/95 transition-[width] duration-300 ease-in-out lg:flex",
        collapsed ? "w-0 overflow-hidden border-r-0" : "w-64 lg:w-72"
      )}
      aria-hidden={collapsed && hydrated}
    >
      {!collapsed && <WorkspacePanel />}
    </div>
  );
}

export default function WorkspacePanelLoader() {
  return (
    <Suspense
      fallback={
        <aside className="hidden w-64 shrink-0 items-center justify-center border-r border-slate-800/80 bg-slate-950/95 lg:flex lg:w-72">
          <LoadingSpinner size="sm" />
        </aside>
      }
    >
      <WorkspacePanelShell />
    </Suspense>
  );
}
