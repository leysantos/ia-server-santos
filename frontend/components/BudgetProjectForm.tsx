"use client";

import { useState } from "react";
import type { BdiObraType, BudgetProjectInfo } from "@/types/api";
import { cn } from "@/lib/utils";
import {
  budgetBtn,
  budgetBtnIcon,
  budgetField,
  budgetFieldActionBtnCol,
  budgetFieldActionRow,
  budgetFieldLabel,
  budgetInput,
  budgetSelect,
} from "@/lib/budget-ui";
import { buildBudgetCode } from "@/lib/budget-code";

export interface ProjectFormValues {
  projeto: string;
  local: string;
  empresa: string;
  responsavel_tecnico: string;
  orcamento: string;
  base_preco: string;
  obra_type: string;
}

interface BudgetProjectFormProps {
  project?: BudgetProjectInfo;
  bdiTypes: BdiObraType[];
  disabled?: boolean;
  existingOrcCodes?: string[];
  onChange: (values: ProjectFormValues) => void;
  onObraTypeChange: (type: string) => void;
}

export function projectToForm(project?: BudgetProjectInfo, obraType = "RF"): ProjectFormValues {
  return {
    projeto: project?.projeto || project?.objeto || "",
    local: project?.local || project?.endereco || "",
    empresa: project?.empresa || project?.orgao || "",
    responsavel_tecnico: project?.responsavel_tecnico || "",
    orcamento: project?.orcamento || "",
    base_preco: project?.base_preco || "",
    obra_type: project?.obra_type || obraType,
  };
}

function pct(rate: number) {
  return `${(rate * 100).toFixed(2).replace(".", ",")}%`;
}

export default function BudgetProjectForm({
  project,
  bdiTypes,
  disabled,
  existingOrcCodes = [],
  onChange,
  onObraTypeChange,
}: BudgetProjectFormProps) {
  const [expanded, setExpanded] = useState(true);
  const values = projectToForm(project, project?.obra_type);
  const set = (patch: Partial<ProjectFormValues>) => onChange({ ...values, ...patch });
  const selectedBdi = bdiTypes.find((t) => t.code === values.obra_type);

  const handleGenerateCode = () => {
    const code = buildBudgetCode(existingOrcCodes, values.empresa, values.orcamento);
    set({ orcamento: code });
  };

  return (
    <div className="overflow-hidden rounded-xl bg-slate-800/30 ring-1 ring-slate-700/50">
      <div className={cn(budgetFieldActionRow, "p-4")}>
        <label className={cn(budgetField, "flex-1")}>
          <span className={budgetFieldLabel}>Nome da obra</span>
          <input
            type="text"
            disabled={disabled}
            value={values.projeto}
            onChange={(e) => set({ projeto: e.target.value })}
            className={budgetInput}
          />
        </label>
        <div className={budgetFieldActionBtnCol}>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={expanded ? "Recolher dados da obra" : "Expandir dados da obra"}
            className={cn(
              budgetBtnIcon,
              "bg-slate-900 text-slate-400 ring-slate-600 hover:bg-slate-800 hover:text-slate-200"
            )}
          >
          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            className={cn("h-5 w-5 transition-transform duration-300", expanded ? "rotate-180" : "rotate-0")}
            aria-hidden
          >
            <path
              fillRule="evenodd"
              d="M5.23 7.21a.75.75 0 011.06.02L10 10.939l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.25a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.08z"
              clipRule="evenodd"
            />
          </svg>
          </button>
        </div>
      </div>

      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-300 ease-in-out",
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="overflow-hidden">
          <div className="grid gap-4 px-4 pb-4 md:grid-cols-2">
            <label className={cn(budgetField, "md:col-span-2")}>
              <span className={budgetFieldLabel}>Código do orçamento</span>
              <div className={budgetFieldActionRow}>
                <input
                  type="text"
                  disabled={disabled}
                  value={values.orcamento}
                  onChange={(e) => set({ orcamento: e.target.value })}
                  placeholder="ORC0001-06/2026-ABC"
                  className={cn(budgetInput, "min-w-0 flex-1 font-mono text-xs")}
                />
                <div className={budgetFieldActionBtnCol}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={handleGenerateCode}
                    className={cn(
                      budgetBtn,
                      "whitespace-nowrap bg-emerald-600/20 text-emerald-300 ring-emerald-500/40 hover:bg-emerald-600/30"
                    )}
                  >
                    Gerar código
                  </button>
                </div>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                Formato: ORC0001-mês/ano-iniciais da empresa
              </p>
            </label>
            <label className={budgetField}>
              <span className={budgetFieldLabel}>Endereço / local</span>
              <input
                type="text"
                disabled={disabled}
                value={values.local}
                onChange={(e) => set({ local: e.target.value })}
                className={budgetInput}
              />
            </label>
            <label className={budgetField}>
              <span className={budgetFieldLabel}>Empresa</span>
              <input
                type="text"
                disabled={disabled}
                value={values.empresa}
                onChange={(e) => set({ empresa: e.target.value })}
                className={budgetInput}
              />
            </label>
            <label className={budgetField}>
              <span className={budgetFieldLabel}>Responsável técnico</span>
              <input
                type="text"
                disabled={disabled}
                value={values.responsavel_tecnico}
                onChange={(e) => set({ responsavel_tecnico: e.target.value })}
                className={budgetInput}
              />
            </label>
            <label className={cn(budgetField, "md:col-span-2")}>
              <span className={budgetFieldLabel}>Tipo de obra (BDI)</span>
              <select
                disabled={disabled}
                value={values.obra_type}
                onChange={(e) => {
                  set({ obra_type: e.target.value });
                  onObraTypeChange(e.target.value);
                }}
                className={cn(budgetSelect, "ring-violet-500/40")}
              >
                {bdiTypes.map((t) => (
                  <option key={t.code} value={t.code}>
                    {t.code} — {t.label} · ComD {pct(t.rate_com_desoneracao)} · SemD{" "}
                    {pct(t.rate_sem_desoneracao)}
                  </option>
                ))}
              </select>
              {selectedBdi && (
                <p className="text-xs text-slate-500">
                  BDI ComD {pct(selectedBdi.rate_com_desoneracao)} · SemD{" "}
                  {pct(selectedBdi.rate_sem_desoneracao)}
                </p>
              )}
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
