"use client";

import type { BudgetSkeleton, BudgetSkeletonEtapa } from "@/types/api";
import { cn } from "@/lib/utils";
import {
  budgetBtn,
  budgetBtnIcon,
  budgetField,
  budgetFieldLabel,
  budgetInput,
  budgetSelect,
  budgetTextarea,
} from "@/lib/budget-ui";

function emptyEtapa(): BudgetSkeletonEtapa {
  return { name: "", sub_etapas: [{ name: "" }] };
}

export interface BudgetSkeletonEditorProps {
  value: {
    name: string;
    description: string;
    obra_type: string;
    etapas: BudgetSkeletonEtapa[];
  };
  bdiTypes: { code: string; label: string }[];
  disabled?: boolean;
  onChange: (next: BudgetSkeletonEditorProps["value"]) => void;
}

export default function BudgetSkeletonEditor({
  value,
  bdiTypes,
  disabled,
  onChange,
}: BudgetSkeletonEditorProps) {
  const updateEtapa = (index: number, patch: Partial<BudgetSkeletonEtapa>) => {
    const etapas = value.etapas.map((e, i) => (i === index ? { ...e, ...patch } : e));
    onChange({ ...value, etapas });
  };

  const updateSub = (etapaIndex: number, subIndex: number, name: string) => {
    const etapas = [...value.etapas];
    const subs = [...(etapas[etapaIndex]?.sub_etapas || [])];
    subs[subIndex] = { name };
    etapas[etapaIndex] = { ...etapas[etapaIndex], sub_etapas: subs };
    onChange({ ...value, etapas });
  };

  const addEtapa = () => {
    onChange({ ...value, etapas: [...value.etapas, emptyEtapa()] });
  };

  const removeEtapa = (index: number) => {
    onChange({ ...value, etapas: value.etapas.filter((_, i) => i !== index) });
  };

  const addSub = (etapaIndex: number) => {
    const etapas = [...value.etapas];
    etapas[etapaIndex] = {
      ...etapas[etapaIndex],
      sub_etapas: [...(etapas[etapaIndex].sub_etapas || []), { name: "" }],
    };
    onChange({ ...value, etapas });
  };

  const removeSub = (etapaIndex: number, subIndex: number) => {
    const etapas = [...value.etapas];
    etapas[etapaIndex] = {
      ...etapas[etapaIndex],
      sub_etapas: etapas[etapaIndex].sub_etapas.filter((_, i) => i !== subIndex),
    };
    onChange({ ...value, etapas });
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className={budgetField}>
          <label className={budgetFieldLabel}>Nome do modelo *</label>
          <input
            className={budgetInput}
            value={value.name}
            disabled={disabled}
            placeholder="Ex.: Reforma de quadra"
            onChange={(e) => onChange({ ...value, name: e.target.value })}
          />
        </div>
        <div className={budgetField}>
          <label className={budgetFieldLabel}>Tipo de obra (BDI)</label>
          <select
            className={budgetSelect}
            value={value.obra_type}
            disabled={disabled}
            onChange={(e) => onChange({ ...value, obra_type: e.target.value })}
          >
            {bdiTypes.map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
            {bdiTypes.length === 0 && (
              <option value={value.obra_type}>{value.obra_type}</option>
            )}
          </select>
        </div>
      </div>

      <div className={budgetField}>
        <label className={budgetFieldLabel}>Descrição</label>
        <textarea
          className={budgetTextarea}
          rows={2}
          value={value.description}
          disabled={disabled}
          placeholder="Quando usar este esqueleto..."
          onChange={(e) => onChange({ ...value, description: e.target.value })}
        />
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-200">Etapas e sub-etapas</h3>
          <button
            type="button"
            disabled={disabled}
            onClick={addEtapa}
            className={cn(budgetBtn, "bg-brand-600/20 px-3 text-brand-300 hover:bg-brand-600/30")}
          >
            + Etapa
          </button>
        </div>

        {value.etapas.length === 0 ? (
          <p className="rounded-xl border border-dashed border-white/10 px-4 py-8 text-center text-sm text-slate-500">
            Adicione pelo menos uma etapa para o esqueleto.
          </p>
        ) : (
          <div className="space-y-4">
            {value.etapas.map((etapa, ei) => (
              <div key={ei} className="app-card space-y-3 p-4">
                <div className="flex gap-2">
                  <div className={cn(budgetField, "flex-1")}>
                    <label className={budgetFieldLabel}>Etapa {ei + 1}</label>
                    <input
                      className={budgetInput}
                      value={etapa.name}
                      disabled={disabled}
                      placeholder="Nome da etapa"
                      onChange={(e) => updateEtapa(ei, { name: e.target.value })}
                    />
                  </div>
                  <div className="flex items-end">
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => removeEtapa(ei)}
                      className={cn(budgetBtnIcon, "text-red-400 hover:bg-red-500/10")}
                      title="Remover etapa"
                    >
                      ×
                    </button>
                  </div>
                </div>

                <div className="ml-2 space-y-2 border-l border-white/10 pl-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                    Sub-etapas
                  </p>
                  {(etapa.sub_etapas || []).map((sub, si) => (
                    <div key={si} className="flex gap-2">
                      <input
                        className={cn(budgetInput, "flex-1")}
                        value={sub.name}
                        disabled={disabled}
                        placeholder={`Sub-etapa ${si + 1}`}
                        onChange={(e) => updateSub(ei, si, e.target.value)}
                      />
                      <button
                        type="button"
                        disabled={disabled}
                        onClick={() => removeSub(ei, si)}
                        className={cn(budgetBtnIcon, "text-slate-500 hover:text-red-400")}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => addSub(ei)}
                    className="text-xs text-brand-400 hover:text-brand-300"
                  >
                    + Sub-etapa
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function skeletonFormFromRecord(sk: BudgetSkeleton | null) {
  if (!sk) {
    return {
      name: "",
      description: "",
      obra_type: "RF",
      etapas: [emptyEtapa()],
    };
  }
  return {
    name: sk.name,
    description: sk.description || "",
    obra_type: sk.obra_type || "RF",
    etapas:
      sk.etapas.length > 0
        ? sk.etapas.map((e) => ({
            name: e.name,
            sub_etapas:
              e.sub_etapas?.length > 0 ? e.sub_etapas.map((s) => ({ name: s.name })) : [{ name: "" }],
          }))
        : [emptyEtapa()],
  };
}

export function skeletonPayloadFromForm(form: ReturnType<typeof skeletonFormFromRecord>) {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    obra_type: form.obra_type,
    etapas: form.etapas
      .map((e) => ({
        name: e.name.trim(),
        sub_etapas: (e.sub_etapas || [])
          .map((s) => ({ name: s.name.trim() }))
          .filter((s) => s.name),
      }))
      .filter((e) => e.name),
  };
}
