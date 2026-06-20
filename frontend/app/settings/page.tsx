"use client";

import Link from "next/link";
import { SETTINGS_MODULES } from "@/components/settings/settings-nav";
import { useSettingsKnowledge } from "@/contexts/SettingsKnowledgeContext";

export default function SettingsOverviewPage() {
  const { stats, catalog } = useSettingsKnowledge();

  const totalChunks = stats?.index?.total_multi_chunks ?? 0;
  const priceBases = catalog?.items.filter((i) => i.has_price_items).length ?? 0;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
          <p className="text-2xl font-bold text-white">{stats?.catalog_total ?? 0}</p>
          <p className="text-xs text-slate-500">Documentos no catálogo</p>
        </div>
        <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
          <p className="text-2xl font-bold text-cyan-400">{totalChunks}</p>
          <p className="text-xs text-slate-500">Chunks FAISS (IA)</p>
        </div>
        <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
          <p className="text-2xl font-bold text-emerald-400">{priceBases}</p>
          <p className="text-xs text-slate-500">Bases de preço</p>
        </div>
      </div>

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h3 className="text-base font-semibold text-white">Atalhos</h3>
        <p className="mt-1 mb-4 text-sm text-slate-500">
          Acesse cada área pelo menu lateral ou pelos cards abaixo.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {SETTINGS_MODULES.filter((m) => m.id !== "overview").map((item) => (
            <Link
              key={item.id}
              href={item.href}
              className="flex items-start gap-3 rounded-xl bg-slate-950/50 p-4 ring-1 ring-slate-800 transition hover:bg-slate-800/40 hover:ring-slate-700"
            >
              <span className="text-cyan-400">{item.icon}</span>
              <span>
                <span className="block text-sm font-medium text-slate-200">{item.label}</span>
                <span className="mt-0.5 block text-xs text-slate-500">{item.description}</span>
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
