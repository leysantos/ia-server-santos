"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "@/services/api";
import {
  formatInstalledModelsLabel,
  getInstalledModelsDisplay,
  type ModelsStatusDisplay,
} from "@/lib/models-status";
import { cn } from "@/lib/utils";

const ModelsStatusContext = createContext<ModelsStatusDisplay | null>(null);

export function ModelsStatusProvider({ children }: { children: ReactNode }) {
  const [display, setDisplay] = useState<ModelsStatusDisplay | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((health) => {
        if (!cancelled) setDisplay(getInstalledModelsDisplay(health));
      })
      .catch(() => {
        if (!cancelled) setDisplay(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ModelsStatusContext.Provider value={display}>{children}</ModelsStatusContext.Provider>
  );
}

/** Rótulo WSL — canto direito do cabeçalho da tela. */
export default function ModelsStatusBadge({ className }: { className?: string }) {
  const display = useContext(ModelsStatusContext);
  if (!display) return null;

  const ariaLabel = `Modelos de IA instalados: ${display.modelsText}`;

  return (
    <p
      className={cn(
        "models-status-badge shrink-0 rounded-xl border border-white/5 bg-surface-card px-3 py-1.5 text-left text-[10px] leading-tight text-slate-500 sm:py-2 sm:text-[11px] lg:whitespace-nowrap max-lg:whitespace-normal",
        className
      )}
      aria-label={ariaLabel}
      title={ariaLabel}
    >
      <span className="font-medium text-slate-400">WSL:</span> {display.modelsText}
    </p>
  );
}

/** Para testes e fallback textual. */
export function modelsStatusLabelFromHealth(
  health: Parameters<typeof getInstalledModelsDisplay>[0]
): string | null {
  return formatInstalledModelsLabel(health);
}
