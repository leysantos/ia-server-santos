"use client";

import { useCallback, useEffect, useState } from "react";

const ITEMS = [
  { id: "4.U1", label: "Esqueleto passarela B12 carregado na UI" },
  { id: "4.U2", label: "Busca CPU — ComD/SemD vs SINAPI oficial" },
  { id: "4.U3", label: "CPU lançada na etapa + total adotado (menor)" },
  { id: "4.U4", label: "Cronograma sync + curvas físico-financeiro" },
  { id: "4.U5", label: "Export .xlsm oficial (PPD SEMINF)" },
  { id: "4.U6", label: "Compliance-pack + checklist L1–L7" },
  { id: "4.U7", label: "Proposta comercial com margem %" },
] as const;

function storageKey(sessionId: string) {
  return `budget-pilot-4u-${sessionId}`;
}

interface BudgetPilotChecklistProps {
  sessionId: string;
}

export default function BudgetPilotChecklist({ sessionId }: BudgetPilotChecklistProps) {
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey(sessionId));
      if (raw) setChecked(JSON.parse(raw) as Record<string, boolean>);
    } catch {
      setChecked({});
    }
  }, [sessionId]);

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      localStorage.setItem(storageKey(sessionId), JSON.stringify(next));
      return next;
    });
  };

  const done = ITEMS.filter((i) => checked[i.id]).length;

  const exportSignoff = useCallback(() => {
    const payload = {
      session_id: sessionId,
      checklist: "§4.U piloto orçamento",
      signed_at: new Date().toISOString(),
      items: ITEMS.map((i) => ({ id: i.id, label: i.label, ok: !!checked[i.id] })),
      progress: `${done}/${ITEMS.length}`,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `piloto-4u-${sessionId.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [sessionId, checked, done]);

  return (
    <div
      className="rounded-xl border border-white/10 bg-surface-raised/40 px-4 py-3"
      data-testid="budget-pilot-checklist"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-200">Piloto §4.U — conferência orçamentista</h3>
        <span className="text-xs text-zinc-400">
          {done}/{ITEMS.length}
        </span>
      </div>
      <ul className="space-y-2 text-sm">
        {ITEMS.map((item) => (
          <li key={item.id} className="flex items-start gap-2">
            <input
              type="checkbox"
              id={item.id}
              checked={!!checked[item.id]}
              onChange={() => toggle(item.id)}
              className="mt-1"
            />
            <label htmlFor={item.id} className="text-zinc-300">
              <span className="font-mono text-xs text-cyan-400">{item.id}</span> — {item.label}
            </label>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={exportSignoff}
        className="mt-3 rounded-lg bg-cyan-600/20 px-3 py-1.5 text-xs text-cyan-200 ring-1 ring-cyan-500/40 hover:bg-cyan-600/30"
      >
        Exportar assinatura JSON
      </button>
    </div>
  );
}
