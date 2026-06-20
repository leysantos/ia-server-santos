"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BudgetRow, BudgetSessionResponse } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetBtn, budgetTextarea } from "@/lib/budget-ui";
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

interface ServiceMemory {
  service: BudgetRow;
  memory: BudgetRow | null;
}

interface MemoryGroup {
  group: BudgetRow;
  services: ServiceMemory[];
  subgroups: MemoryGroup[];
}

function directServices(rows: BudgetRow[], groupCode: string): BudgetRow[] {
  return rows.filter(
    (r) => r.row_type === "S" && !r.is_memory_row && r.parent_code === groupCode
  );
}

function subetapas(rows: BudgetRow[], parentCode: string): BudgetRow[] {
  return rows.filter((r) => r.row_type === "SUB-ETAPA" && r.parent_code === parentCode);
}

function memoryForService(rows: BudgetRow[], serviceCode: string): BudgetRow | null {
  return (
    rows.find((r) => r.is_memory_row && r.parent_code === serviceCode) ??
    rows.find((r) => r.is_memory_row && r.code.startsWith(`${serviceCode}.`)) ??
    null
  );
}

function buildMemoryTree(rows: BudgetRow[]): MemoryGroup[] {
  const etapas = rows.filter((r) => r.row_type === "ETAPA" && r.level === 0);

  const buildGroup = (group: BudgetRow): MemoryGroup => ({
    group,
    services: directServices(rows, group.code).map((service) => ({
      service,
      memory: memoryForService(rows, service.code),
    })),
    subgroups: subetapas(rows, group.code).map(buildGroup),
  });

  return etapas.map(buildGroup);
}

function countServices(group: MemoryGroup): number {
  return (
    group.services.length +
    group.subgroups.reduce((sum, sub) => sum + countServices(sub), 0)
  );
}

function countMemories(group: MemoryGroup): number {
  const here = group.services.filter((s) => s.memory).length;
  return here + group.subgroups.reduce((sum, sub) => sum + countMemories(sub), 0);
}

function fmtQty(n: number) {
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 4 });
}

function MemoryServiceRow({
  item,
  editingId,
  draft,
  saving,
  onCellEdit,
  onStartEdit,
  onDraftChange,
  onSave,
  onCancel,
}: {
  item: ServiceMemory;
  editingId: string | null;
  draft: string;
  saving: boolean;
  onCellEdit?: BudgetMemoryPanelProps["onCellEdit"];
  onStartEdit: (memory: BudgetRow, text: string) => void;
  onDraftChange: (value: string) => void;
  onSave: (row: BudgetRow) => void;
  onCancel: () => void;
}) {
  const { service, memory } = item;
  const isEditing = memory ? editingId === memory.row_id : false;

  return (
    <article className="rounded-lg bg-slate-900/50 px-3 py-3 ring-1 ring-slate-700/50">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="font-mono text-xs text-cyan-400">{service.code}</span>
        <span className="text-sm font-medium text-slate-200">{service.name}</span>
        <span className="text-xs text-slate-500">
          {fmtQty(service.quantity)} {service.unit}
        </span>
      </div>

      {memory ? (
        isEditing ? (
          <div className="flex gap-2">
            <textarea
              autoFocus
              value={draft}
              onChange={(e) => onDraftChange(e.target.value)}
              rows={3}
              className={cn(budgetTextarea, "flex-1 text-sm ring-cyan-500/50")}
            />
            <div className="flex shrink-0 flex-col gap-1">
              <button
                type="button"
                onClick={() => onSave(memory)}
                disabled={saving}
                className={cn(budgetBtn, "bg-cyan-600/30 text-cyan-300 ring-cyan-500/40")}
              >
                Salvar
              </button>
              <button
                type="button"
                onClick={onCancel}
                className={cn(budgetBtn, "bg-slate-700/50 text-slate-400 ring-slate-600")}
              >
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <p
            className={cn(
              "rounded-md bg-slate-950/60 px-3 py-2 text-sm leading-relaxed text-slate-300",
              onCellEdit && "cursor-text hover:text-cyan-300"
            )}
            onClick={() => {
              if (!onCellEdit) return;
              onStartEdit(memory, memory.calculation_note || memory.name);
            }}
          >
            <span className="mr-1 text-slate-500">MCQ:</span>
            {memory.calculation_note || memory.name}
          </p>
        )
      ) : (
        <p className="rounded-md border border-dashed border-slate-700/80 px-3 py-2 text-xs italic text-slate-500">
          Sem memória de cálculo — use MC ou IA no cabeçalho da etapa/sub-etapa.
        </p>
      )}
    </article>
  );
}

function MemoryGroupSection({
  node,
  depth,
  generating,
  onGenerateGroup,
  editingId,
  draft,
  saving,
  onCellEdit,
  onStartEdit,
  onDraftChange,
  onSave,
  onCancel,
}: {
  node: MemoryGroup;
  depth: number;
  generating: boolean;
  onGenerateGroup: (groupCode: string, useLlm: boolean) => void;
  editingId: string | null;
  draft: string;
  saving: boolean;
  onCellEdit?: BudgetMemoryPanelProps["onCellEdit"];
  onStartEdit: (memory: BudgetRow, text: string) => void;
  onDraftChange: (value: string) => void;
  onSave: (row: BudgetRow) => void;
  onCancel: () => void;
}) {
  const isEtapa = node.group.row_type === "ETAPA";
  const serviceCount = countServices(node);
  const memoryCount = countMemories(node);
  const border = isEtapa ? "ring-violet-500/30" : "ring-cyan-500/20";

  if (serviceCount === 0 && node.subgroups.length === 0) return null;

  return (
    <section className={cn("overflow-hidden rounded-xl bg-slate-800/30 ring-1", border)}>
      <header
        className={cn(
          "flex flex-wrap items-center justify-between gap-2 border-b border-slate-700/50 bg-slate-900/40 px-4 py-3",
          depth > 0 && "pl-6"
        )}
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "shrink-0 font-mono text-xs",
                isEtapa ? "text-violet-400" : "text-cyan-400"
              )}
            >
              {isEtapa ? "ETAPA" : "SUB"} {node.group.code}
            </span>
            <h3 className="truncate text-sm font-semibold uppercase text-white">
              {node.group.name}
            </h3>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            {serviceCount} composição(ões) · {memoryCount} com MCQ
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            disabled={generating || serviceCount === 0}
            onClick={() => onGenerateGroup(node.group.code, false)}
            className={cn(
              budgetBtn,
              "bg-amber-600/20 text-amber-300 ring-amber-500/40 hover:bg-amber-600/30"
            )}
          >
            MC
          </button>
          <button
            type="button"
            disabled={generating || serviceCount === 0}
            onClick={() => onGenerateGroup(node.group.code, true)}
            className={cn(
              budgetBtn,
              "bg-violet-600/20 text-violet-300 ring-violet-500/40 hover:bg-violet-600/30"
            )}
          >
            IA
          </button>
        </div>
      </header>

      <div className={cn("space-y-3 p-4", depth > 0 && "pl-6")}>
        {node.services.length > 0 && (
          <div className="space-y-2">
            {node.services.map((item) => (
              <MemoryServiceRow
                key={item.service.row_id}
                item={item}
                editingId={editingId}
                draft={draft}
                saving={saving}
                onCellEdit={onCellEdit}
                onStartEdit={onStartEdit}
                onDraftChange={onDraftChange}
                onSave={onSave}
                onCancel={onCancel}
              />
            ))}
          </div>
        )}

        {node.subgroups.map((sub) => (
          <MemoryGroupSection
            key={sub.group.row_id}
            node={sub}
            depth={depth + 1}
            generating={generating}
            onGenerateGroup={onGenerateGroup}
            editingId={editingId}
            draft={draft}
            saving={saving}
            onCellEdit={onCellEdit}
            onStartEdit={onStartEdit}
            onDraftChange={onDraftChange}
            onSave={onSave}
            onCancel={onCancel}
          />
        ))}

        {node.services.length === 0 && node.subgroups.length === 0 && (
          <p className="text-center text-xs text-slate-500 py-2">
            Nenhuma composição nesta {isEtapa ? "etapa" : "sub-etapa"}.
          </p>
        )}
      </div>
    </section>
  );
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

  const tree = useMemo(() => buildMemoryTree(session.rows), [session.rows]);

  const totalServices = useMemo(
    () => tree.reduce((sum, node) => sum + countServices(node), 0),
    [tree]
  );

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
        <ModelSelector id="memory-panel-model" value={llmModel} onChange={setLlmModel} />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={loading || generating || totalServices === 0}
            onClick={() => handleGenerateAll(false)}
            className={cn(
              budgetBtn,
              "bg-amber-600/20 px-4 text-sm text-amber-300 ring-amber-500/40 hover:bg-amber-600/30 disabled:opacity-50"
            )}
          >
            Gerar MC — obra inteira (regras)
          </button>
          <button
            type="button"
            disabled={loading || generating || totalServices === 0}
            onClick={() => handleGenerateAll(true)}
            className={cn(
              budgetBtn,
              "bg-violet-600/20 px-4 text-sm text-violet-300 ring-violet-500/40 hover:bg-violet-600/30 disabled:opacity-50"
            )}
          >
            Gerar MC — obra inteira (IA)
          </button>
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wider text-cyan-400">
            Memória de cálculo — MCQ
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Organizada por etapa e sub-etapa, com cada composição e sua memória vinculada.
          </p>
        </div>

        {tree.length === 0 ? (
          <p className="rounded-xl bg-slate-800/40 px-4 py-8 text-center text-sm text-slate-500 ring-1 ring-slate-700/60">
            Adicione etapas e serviços para gerar as memórias de cálculo.
          </p>
        ) : (
          tree.map((node) => (
            <MemoryGroupSection
              key={node.group.row_id}
              node={node}
              depth={0}
              generating={generating}
              onGenerateGroup={handleGenerateGroup}
              editingId={editingId}
              draft={draft}
              saving={saving}
              onCellEdit={onCellEdit}
              onStartEdit={(memory, text) => {
                setDraft(text);
                setEditingId(memory.row_id);
              }}
              onDraftChange={setDraft}
              onSave={handleSave}
              onCancel={() => setEditingId(null)}
            />
          ))
        )}
      </section>
    </div>
  );
}
