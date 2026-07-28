"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
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

function shortenModelsText(modelsText: string, maxVisible = 2): string {
  const parts = modelsText
    .split("·")
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length <= maxVisible) return modelsText;
  const rest = parts.length - maxVisible;
  return `${parts.slice(0, maxVisible).join(" · ")} · +${rest}`;
}

/** Rótulo WSL — canto direito do cabeçalho da tela. */
export default function ModelsStatusBadge({ className }: { className?: string }) {
  const display = useContext(ModelsStatusContext);
  const shortText = useMemo(
    () => (display ? shortenModelsText(display.modelsText, 2) : ""),
    [display]
  );

  if (!display) return null;

  const ariaLabel = `Modelos de IA instalados: ${display.modelsText}`;

  return (
    <p
      className={cn(
        "models-status-badge min-w-0 max-w-full truncate rounded-xl border border-white/5 bg-surface-card px-3 py-1.5 text-left text-[10px] leading-snug text-slate-500 sm:max-w-md sm:text-[11px]",
        className
      )}
      aria-label={ariaLabel}
      title={ariaLabel}
    >
      <span className="font-medium text-slate-400">WSL:</span> {shortText}
    </p>
  );
}

/** Para testes e fallback textual. */
export function modelsStatusLabelFromHealth(
  health: Parameters<typeof getInstalledModelsDisplay>[0]
): string | null {
  return formatInstalledModelsLabel(health);
}
