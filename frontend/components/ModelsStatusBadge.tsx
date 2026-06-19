"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "@/services/api";
import { formatInstalledModelsLabel } from "@/lib/models-status";

const ModelsStatusContext = createContext<string | null>(null);

export function ModelsStatusProvider({ children }: { children: ReactNode }) {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((health) => {
        if (!cancelled) setLabel(formatInstalledModelsLabel(health));
      })
      .catch(() => {
        if (!cancelled) setLabel(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ModelsStatusContext.Provider value={label}>{children}</ModelsStatusContext.Provider>
  );
}

/** Rótulo WSL — canto direito do cabeçalho da tela. */
export default function ModelsStatusBadge() {
  const label = useContext(ModelsStatusContext);
  if (!label) return null;

  return (
    <p
      className="inline-flex max-w-[min(100vw-2rem,42rem)] items-center rounded-xl bg-slate-800/80 px-3 py-2 text-right text-[11px] leading-snug text-slate-500 ring-1 ring-slate-700/80"
      aria-label="Modelos de IA instalados"
    >
      {label}
    </p>
  );
}
