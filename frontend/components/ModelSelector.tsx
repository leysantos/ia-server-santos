"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import { cn } from "@/lib/utils";

interface ModelSelectorProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  id?: string;
}

function isLlmModel(name: string): boolean {
  return !name.toLowerCase().includes("embed");
}

function formatModelLabel(name: string): string {
  return name.replace(/:latest$/, "");
}

export default function ModelSelector({ value, onChange, className, id }: ModelSelectorProps) {
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .modelsStatus()
      .then((status) => {
        if (cancelled) return;
        const installed = (status.installed_models ?? []).filter(isLlmModel);
        setModels(installed);
      })
      .catch(() => {
        if (!cancelled) setModels([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const options = useMemo(() => {
    const seen = new Set<string>();
    const list: { value: string; label: string }[] = [{ value: "auto", label: "Auto (roteamento)" }];
    for (const name of models) {
      const key = formatModelLabel(name);
      if (seen.has(key)) continue;
      seen.add(key);
      list.push({ value: name, label: key });
    }
    if (value !== "auto" && value && !list.some((o) => o.value === value)) {
      list.push({ value, label: formatModelLabel(value) });
    }
    return list;
  }, [models, value]);

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <label htmlFor={id} className="shrink-0 text-xs text-slate-500">
        Modelo IA
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading && models.length === 0}
        className="h-8 min-w-0 flex-1 rounded-lg bg-slate-900 px-2 text-xs text-slate-200 ring-1 ring-slate-600 focus:outline-none focus:ring-cyan-500/40 disabled:opacity-50 sm:max-w-xs sm:flex-none"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
