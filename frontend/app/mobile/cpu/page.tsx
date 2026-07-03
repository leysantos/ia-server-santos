"use client";

import Link from "next/link";
import BudgetCpuSearchTab from "@/components/BudgetCpuSearchTab";
import MobilePageShell from "@/components/mobile/MobilePageShell";

export default function MobileCpuPage() {
  return (
    <MobilePageShell
      title="Consultar CPU"
      subtitle="Composição aberta · exportar PDF"
      trailing={
        <Link
          href="/budget?tab=busca_cpu"
          className="shrink-0 rounded-lg px-2 py-1 text-xs text-cyan-400 ring-1 ring-cyan-500/30"
        >
          Desktop
        </Link>
      }
    >
      <div className="mx-auto max-w-lg">
        <BudgetCpuSearchTab />
      </div>
    </MobilePageShell>
  );
}
