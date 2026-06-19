"use client";

import { Suspense } from "react";
import { usePathname } from "next/navigation";
import WorkspacePanel from "@/components/WorkspacePanel";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useWorkspaceShell } from "@/components/WorkspaceShellContext";
import { cn } from "@/lib/utils";

function WorkspacePanelShell() {
  const pathname = usePathname();
  const { collapsed, hydrated } = useWorkspaceShell();
  const showPanel = pathname === "/chat" || pathname.startsWith("/projects");

  if (!showPanel) return null;

  return (
    <div
      className={cn(
        "relative flex h-full shrink-0 flex-col border-r border-slate-800/80 bg-slate-950/95 transition-[width] duration-300 ease-in-out",
        collapsed ? "w-0 overflow-hidden border-r-0" : "w-72"
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
        <aside className="flex w-72 shrink-0 items-center justify-center border-r border-slate-800/80 bg-slate-950/95">
          <LoadingSpinner size="sm" />
        </aside>
      }
    >
      <WorkspacePanelShell />
    </Suspense>
  );
}
