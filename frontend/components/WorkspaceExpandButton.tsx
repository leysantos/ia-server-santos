"use client";

import { usePathname } from "next/navigation";
import { useWorkspaceShell } from "@/components/WorkspaceShellContext";
import { cn } from "@/lib/utils";

interface WorkspaceExpandButtonProps {
  className?: string;
}

/** Botão para reabrir o painel de conversas quando colapsado. */
export default function WorkspaceExpandButton({ className }: WorkspaceExpandButtonProps) {
  const pathname = usePathname();
  const { collapsed, toggle, hydrated } = useWorkspaceShell();
  const showPanel = pathname === "/chat" || pathname.startsWith("/projects");

  if (!showPanel || !hydrated || !collapsed) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      className={cn("panel-collapse-btn", className)}
      title="Mostrar conversas"
      aria-label="Mostrar painel de conversas"
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </button>
  );
}

interface WorkspaceCollapseStripProps {
  className?: string;
}

/** Faixa lateral fina quando o painel está oculto — clique expande. */
export function WorkspaceCollapseStrip({ className }: WorkspaceCollapseStripProps) {
  const pathname = usePathname();
  const { collapsed, toggle, hydrated } = useWorkspaceShell();
  const showPanel = pathname === "/chat" || pathname.startsWith("/projects");

  if (!showPanel || !hydrated || !collapsed) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      className={cn(
        "group absolute bottom-0 left-0 top-0 z-10 flex w-3 flex-col items-center justify-center border-r border-slate-800/60 bg-slate-950/80 transition hover:w-4 hover:bg-slate-900/90",
        className
      )}
      title="Mostrar conversas"
      aria-label="Mostrar painel de conversas"
    >
      <svg
        className="h-3.5 w-3.5 text-slate-600 transition group-hover:text-cyan-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </button>
  );
}
