"use client";

import { useEffect, useState } from "react";
import { request } from "@/services/api/http";

interface CompanyItem {
  id: string;
  nome: string;
  slug: string;
}

const STORAGE_KEY = "ia_tenant_id";

export function getStoredTenantId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY);
}

export default function BudgetTenantSelector() {
  const [companies, setCompanies] = useState<CompanyItem[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setSelected(getStoredTenantId() ?? "");
    void request<{ items: CompanyItem[] }>("/workflow/companies")
      .then((res) => setCompanies(res.items ?? []))
      .catch(() => setCompanies([]))
      .finally(() => setLoading(false));
  }, []);

  const onChange = (id: string) => {
    setSelected(id);
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  };

  if (loading) return null;
  if (companies.length === 0) return null;

  return (
    <div
      className="rounded-xl border border-white/10 bg-surface-raised/40 px-4 py-3"
      data-testid="budget-tenant-selector"
    >
      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-400">
        Empresa (tenant)
      </label>
      <select
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-white/10 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-100"
      >
        <option value="">— Todas / legado —</option>
        {companies.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nome}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-zinc-500">
        Orçamentos salvos ficam isolados por empresa quando selecionada (B27).
      </p>
    </div>
  );
}
