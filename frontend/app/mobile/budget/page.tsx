"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import MobilePageShell from "@/components/mobile/MobilePageShell";
import MobileExportPdfButton from "@/components/mobile/MobileExportPdfButton";
import { EXPORT_DOCS } from "@/components/BudgetToolbar";
import { api, downloadApiFile } from "@/services/api";
import type { BudgetSummary } from "@/types/api";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/utils";

function fmtMoney(n: number) {
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function MobileBudgetPage() {
  return (
    <Suspense fallback={<MobilePageShell title="Orçamentos"><p className="text-sm text-slate-500">Carregando…</p></MobilePageShell>}>
      <MobileBudgetContent />
    </Suspense>
  );
}

function MobileBudgetContent() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project");
  const [items, setItems] = useState<BudgetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [exportDoc, setExportDoc] = useState<string>(EXPORT_DOCS[0].key);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.pricingListSaved(projectId ?? undefined);
      setItems(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar orçamentos");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = items.filter((item) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return [item.title, item.orcamento, item.obra_type].filter(Boolean).join(" ").toLowerCase().includes(q);
  });

  const handleExport = async (savedId: string) => {
    setError(null);
    const payload = await api.pricingGetSaved(savedId);
    const restored = await api.pricingRestoreSession(payload);
    const doc = EXPORT_DOCS.find((d) => d.key === exportDoc);
    await downloadApiFile(
      `/pricing/budget/${restored.session_id}/export/pdf/${exportDoc}`,
      `${exportDoc.toUpperCase()}_${restored.session_id.slice(0, 8)}.pdf`
    );
    void doc;
  };

  return (
    <MobilePageShell
      title="Orçamentos"
      subtitle="Localize e gere relatórios em PDF"
      trailing={
        <Link
          href="/budget"
          className="shrink-0 rounded-lg px-2 py-1 text-xs text-cyan-400 ring-1 ring-cyan-500/30"
        >
          Desktop
        </Link>
      }
    >
      <div className="mx-auto max-w-lg space-y-4">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar orçamento…"
          className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
        />

        {error && <p className="text-sm text-red-300">{error}</p>}

        {loading ? (
          <p className="text-sm text-slate-500">Carregando…</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhum orçamento salvo encontrado.</p>
        ) : (
          <ul className="space-y-2">
            {filtered.map((item) => {
              const open = expandedId === item.id;
              return (
                <li
                  key={item.id}
                  className="overflow-hidden rounded-xl bg-slate-900/60 ring-1 ring-slate-800"
                >
                  <button
                    type="button"
                    onClick={() => setExpandedId(open ? null : item.id)}
                    className="flex w-full items-start gap-3 px-4 py-3 text-left"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white">{item.title}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {fmtMoney(item.grand_total)}
                        {item.updated_at ? ` · ${formatDate(item.updated_at)}` : ""}
                      </p>
                    </div>
                    <span className={cn("text-slate-500 transition", open && "rotate-180")}>▾</span>
                  </button>
                  {open && (
                    <div className="space-y-3 border-t border-slate-800 px-4 py-3">
                      <label className="block text-xs text-slate-400">
                        Relatório
                        <select
                          value={exportDoc}
                          onChange={(e) => setExportDoc(e.target.value)}
                          className="mt-1 w-full rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
                        >
                          {EXPORT_DOCS.map((d) => (
                            <option key={d.key} value={d.key}>
                              {d.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <MobileExportPdfButton onExport={() => handleExport(item.id)} />
                      <Link
                        href={`/budget?saved=${item.id}`}
                        className="block text-center text-xs text-cyan-400 hover:underline"
                      >
                        Abrir no editor completo
                      </Link>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </MobilePageShell>
  );
}
