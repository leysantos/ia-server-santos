"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BudgetRow, BudgetSessionResponse } from "@/types/api";
import { cn } from "@/lib/utils";
import ModelSelector from "@/components/ModelSelector";
import { useLlmModelSelection } from "@/hooks/useLlmModel";

interface BudgetMemoryPanelProps {
  session: BudgetSessionResponse;
  loading?: boolean;
  onUpdate: (session: BudgetSessionResponse) => void;
  onCellEdit?: (
    rowId: string,
    field: string,
    value: number | string,
    code?: string
  ) => Promise<BudgetSessionResponse>;
}

export default function BudgetMemoryPanel({
  session,
  loading,
  onUpdate,
  onCellEdit,
}: BudgetMemoryPanelProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const { model: llmModel, setModel: setLlmModel } = useLlmModelSelection();

  const memoryRows = session.rows.filter(
    (r) => r.is_memory_row || r.row_type === "MEMORIA"
  );

  const groups = useMemo(() => {
    const etapas = session.rows.filter((r) => r.row_type === "ETAPA");
    const subs = session.rows.filter((r) => r.row_type === "SUB-ETAPA");
    return [...etapas, ...subs];
  }, [session.rows]);

  const parentService = (row: BudgetRow) => {
    const parentCode = session.rows.find((r) => r.row_id === row.row_id)?.code;
    const mem = row;
    for (const r of session.rows) {
      if (r.row_type === "S" && !r.is_memory_row && mem.code.startsWith(`${r.code}.`)) {
        return r;
      }
    }
    const idx = session.rows.findIndex((r) => r.row_id === row.row_id);
    for (let i = idx - 1; i >= 0; i--) {
      const r = session.rows[i];
      if (r.row_type === "S" && !r.is_memory_row) return r;
    }
    return null;
  };

  const groupForService = (svc: BudgetRow | null) => {
    if (!svc?.parent_code) return null;
    return session.rows.find((r) => r.code === svc.parent_code && r.row_type !== "S") || null;
  };

  const handleSave = useCallback(
    async (row: BudgetRow) => {
      if (!onCellEdit) return;
      setSaving(true);
      try {
        const updated = await onCellEdit(row.row_id, "calculation_note", draft, row.code);
        onUpdate(updated);
        setEditingId(null);
      } finally {
        setSaving(false);
      }
    },
    [draft, onCellEdit, onUpdate]
  );

  const handleGenerateAll = async (useLlm: boolean) => {
    setGenerating(true);
    try {
      const res = await api.pricingGenerateMemories(
        session.session_id,
        undefined,
        useLlm,
        useLlm ? llmModel : undefined
      );
      onUpdate(res.session);
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateGroup = async (groupCode: string, useLlm: boolean) => {
    setGenerating(true);
    try {
      const res = await api.pricingGenerateMemories(
        session.session_id,
        groupCode,
        useLlm,
        useLlm ? llmModel : undefined
      );
      onUpdate(res.session);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-xl bg-slate-800/40 p-4 ring-1 ring-slate-700/60">
        <ModelSelector
          id="memory-panel-model"
          value={llmModel}
          onChange={setLlmModel}
        />
        <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={loading || generating || memoryRows.length === 0}
          onClick={() => handleGenerateAll(false)}
          className="rounded-lg bg-amber-600/20 px-4 py-2 text-sm text-amber-300 ring-1 ring-amber-500/40 disabled:opacity-50"
        >
          Gerar MC — obra inteira (regras)
        </button>
        <button
          type="button"
          disabled={loading || generating}
          onClick={() => handleGenerateAll(true)}
          className="rounded-lg bg-violet-600/20 px-4 py-2 text-sm text-violet-300 ring-1 ring-violet-500/40 disabled:opacity-50"
        >
          Gerar MC — obra inteira (IA)
        </button>
        </div>
      </section>

      {groups.length > 0 && (
        <section className="rounded-xl bg-slate-800/30 p-4 ring-1 ring-slate-700/50">
          <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-400">
            Por etapa / sub-etapa
          </h3>
          <div className="flex flex-wrap gap-2">
            {groups.map((g) => (
              <div key={g.row_id} className="flex gap-1 rounded-lg bg-slate-900/60 p-1 ring-1 ring-slate-700/40">
                <span className="px-2 py-1 text-xs text-slate-400">{g.code}</span>
                <button
                  type="button"
                  disabled={generating}
                  onClick={() => handleGenerateGroup(g.code, false)}
                  className="rounded px-2 py-1 text-xs text-amber-300 hover:bg-amber-500/10 disabled:opacity-50"
                >
                  MC
                </button>
                <button
                  type="button"
                  disabled={generating}
                  onClick={() => handleGenerateGroup(g.code, true)}
                  className="rounded px-2 py-1 text-xs text-violet-300 hover:bg-violet-500/10 disabled:opacity-50"
                >
                  IA
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-xl bg-slate-800/40 ring-1 ring-slate-700/60">
        <div className="border-b border-slate-700/60 px-4 py-3">
          <h3 className="text-xs font-medium uppercase tracking-wider text-cyan-400">
            Memória de cálculo — MCQ
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Edite manualmente ou gere automaticamente. Cada serviço possui linha de memória vinculada.
          </p>
        </div>

        {memoryRows.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-slate-500">
            Adicione serviços nas etapas e gere as memórias de cálculo.
          </p>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {memoryRows.map((row) => {
              const parent = parentService(row);
              const group = groupForService(parent);
              const isEditing = editingId === row.row_id;
              return (
                <div key={row.row_id} className="px-4 py-3 hover:bg-slate-800/20">
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    {group && (
                      <span className="rounded bg-violet-500/10 px-1.5 py-0.5 text-violet-300">
                        {group.code} {group.name.slice(0, 30)}
                      </span>
                    )}
                    {parent && (
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono">
                        {parent.code} — {parent.name.slice(0, 36)}
                        {parent.name.length > 36 ? "…" : ""}
                      </span>
                    )}
                  </div>
                  {isEditing ? (
                    <div className="flex gap-2">
                      <textarea
                        autoFocus
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        rows={3}
                        className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-200 ring-1 ring-cyan-500/50"
                      />
                      <div className="flex flex-col gap-1">
                        <button
                          type="button"
                          onClick={() => handleSave(row)}
                          disabled={saving}
                          className="rounded bg-cyan-600/30 px-3 py-1 text-xs text-cyan-300"
                        >
                          Salvar
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingId(null)}
                          className="rounded bg-slate-700/50 px-3 py-1 text-xs text-slate-400"
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p
                      className={cn(
                        "cursor-text text-sm text-slate-300",
                        onCellEdit && "hover:text-cyan-300"
                      )}
                      onClick={() => {
                        if (!onCellEdit) return;
                        setDraft(row.calculation_note || row.name);
                        setEditingId(row.row_id);
                      }}
                    >
                      ↳ {row.calculation_note || row.name}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
