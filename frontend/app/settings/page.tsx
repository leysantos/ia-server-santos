"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SETTINGS_MODULES } from "@/components/settings/settings-nav";
import { useSettingsKnowledge } from "@/contexts/SettingsKnowledgeContext";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { PriceBankInventory } from "@/types/api";

export default function SettingsOverviewPage() {
  const { stats } = useSettingsKnowledge();
  const [priceBank, setPriceBank] = useState<PriceBankInventory | null>(null);

  useEffect(() => {
    api
      .pricingSyncBankInventory()
      .then(setPriceBank)
      .catch(() => setPriceBank(null));
  }, []);

  const totalChunks = stats?.index?.total_multi_chunks ?? 0;
  const priceBaseSources = priceBank?.source_count ?? 0;
  const priceBasePeriods = priceBank?.period_count ?? 0;
  const nbrCov = stats?.nbr_coverage;
  const nbrLow = nbrCov && nbrCov.catalog_codes > 0 && nbrCov.coverage_pct < 95;

  return (
    <div className="space-y-6">
      {nbrLow && (
        <div className="rounded-xl bg-amber-500/10 p-4 ring-1 ring-amber-500/40">
          <p className="text-sm font-medium text-amber-200">
            Indexação NBR incompleta — {nbrCov.coverage_pct}% de cobertura (
            {nbrCov.not_indexed_codes} códigos pendentes)
          </p>
          <p className="mt-1 text-xs text-slate-400">
            <Link href="/settings/indexing" className="text-amber-300 hover:underline">
              Ir para Indexação FAISS
            </Link>{" "}
            para completar o índice RAG.
          </p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
          <p className="text-2xl font-bold text-white">{stats?.catalog_total ?? 0}</p>
          <p className="text-xs text-slate-500">Documentos no catálogo</p>
        </div>
        <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
          <p className="text-2xl font-bold text-cyan-400">{totalChunks}</p>
          <p className="text-xs text-slate-500">Chunks FAISS (IA)</p>
        </div>
        <div
          className={cn(
            "rounded-xl p-4 ring-1",
            nbrLow ? "bg-amber-500/10 ring-amber-500/30" : "bg-slate-900/60 ring-slate-800",
          )}
        >
          <p
            className={cn(
              "text-2xl font-bold",
              nbrLow ? "text-amber-300" : "text-blue-300",
            )}
          >
            {nbrCov ? `${nbrCov.coverage_pct}%` : "—"}
          </p>
          <p className="text-xs text-slate-500">Cobertura NBR no FAISS</p>
        </div>
        <div className="rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
          <p className="text-2xl font-bold text-emerald-400">{priceBaseSources}</p>
          <p className="text-xs text-slate-500">Bases de preço</p>
          {priceBasePeriods > 0 && (
            <p className="mt-0.5 text-xs text-slate-600">
              {priceBasePeriods.toLocaleString("pt-BR")} período(s) importado(s)
            </p>
          )}
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
