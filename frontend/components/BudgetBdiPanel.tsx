"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BdiEditalProfile, BdiTcuComponents, BdiValidationResult, BudgetProjectInfo } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetBtn, budgetField, budgetFieldLabel, budgetInput, budgetSelect } from "@/lib/budget-ui";

const TCU_FIELDS: { key: keyof BdiTcuComponents; label: string }[] = [
  { key: "administracao_central", label: "AC — Administração central" },
  { key: "garantias_seguros", label: "G — Garantias e seguros" },
  { key: "riscos", label: "R — Riscos" },
  { key: "despesas_financeiras", label: "DF — Despesas financeiras" },
  { key: "lucro", label: "L — Lucro" },
  { key: "tributos", label: "T — Tributos" },
];

function pct(rate: number) {
  return `${(rate * 100).toFixed(2).replace(".", ",")}%`;
}

function emptyComponents(): BdiTcuComponents {
  return {
    administracao_central: 0,
    garantias_seguros: 0,
    riscos: 0,
    despesas_financeiras: 0,
    lucro: 0,
    tributos: 0,
  };
}

interface BudgetBdiPanelProps {
  sessionId: string;
  project?: BudgetProjectInfo;
  disabled?: boolean;
  onUpdated: (session: Awaited<ReturnType<typeof api.pricingUpdateBdiConfig>>) => void;
  onError?: (err: unknown) => void;
}

export default function BudgetBdiPanel({
  sessionId,
  project,
  disabled,
  onUpdated,
  onError,
}: BudgetBdiPanelProps) {
  const [profiles, setProfiles] = useState<BdiEditalProfile[]>([]);
  const [profileId, setProfileId] = useState(project?.bdi?.profile_id ?? "seminf_table");
  const [componentsComd, setComponentsComd] = useState<BdiTcuComponents>(
    project?.bdi?.components_comd ?? emptyComponents()
  );
  const [componentsSemd, setComponentsSemd] = useState<BdiTcuComponents>(
    project?.bdi?.components_semd ?? emptyComponents()
  );
  const [saving, setSaving] = useState(false);
  const [validation, setValidation] = useState<BdiValidationResult | null>(null);

  const loadValidation = useCallback(async () => {
    try {
      const result = await api.pricingBdiValidation(sessionId);
      setValidation(result);
    } catch {
      setValidation(null);
    }
  }, [sessionId]);

  useEffect(() => {
    void loadValidation();
  }, [loadValidation, project?.bdi]);

  useEffect(() => {
    api.pricingBdiProfiles().then((r) => setProfiles(r.profiles)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!project?.bdi) return;
    setProfileId(project.bdi.profile_id ?? "seminf_table");
    if (project.bdi.components_comd) setComponentsComd(project.bdi.components_comd);
    if (project.bdi.components_semd) setComponentsSemd(project.bdi.components_semd);
  }, [project?.bdi]);

  const selectedProfile = useMemo(
    () => profiles.find((p) => p.id === profileId),
    [profiles, profileId]
  );

  const previewRates = useMemo(() => {
    if (project?.bdi?.rate_com_desoneracao != null) {
      return {
        comd: project.bdi.rate_com_desoneracao,
        semd: project.bdi.rate_sem_desoneracao,
      };
    }
    return selectedProfile
      ? {
          comd: selectedProfile.rate_com_desoneracao,
          semd: selectedProfile.rate_sem_desoneracao,
        }
      : { comd: 0, semd: 0 };
  }, [project?.bdi, selectedProfile]);

  const applyProfile = useCallback(async () => {
    setSaving(true);
    try {
      const body: Parameters<typeof api.pricingUpdateBdiConfig>[1] = {
        profile_id: profileId,
        obra_type: project?.obra_type,
      };
      if (profileId === "custom_edital") {
        body.source = "custom";
        body.components_comd = componentsComd;
        body.components_semd = componentsSemd;
      }
      const updated = await api.pricingUpdateBdiConfig(sessionId, body);
      onUpdated(updated);
      await loadValidation();
    } catch (err) {
      onError?.(err);
    } finally {
      setSaving(false);
    }
  }, [sessionId, profileId, project?.obra_type, componentsComd, componentsSemd, onUpdated, onError, loadValidation]);

  const renderComponentGrid = (
    title: string,
    values: BdiTcuComponents,
    onChange: (next: BdiTcuComponents) => void
  ) => (
    <div className="rounded-lg border border-white/5 bg-slate-900/40 p-3">
      <p className="text-xs font-medium text-slate-300">{title}</p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {TCU_FIELDS.map(({ key, label }) => (
          <label key={key} className={budgetField}>
            <span className="text-[10px] text-slate-500">{label}</span>
            <input
              type="number"
              step="0.001"
              min={0}
              max={0.99}
              disabled={disabled || saving || profileId !== "custom_edital"}
              value={values[key]}
              onChange={(e) => onChange({ ...values, [key]: Number(e.target.value) || 0 })}
              className={cn(budgetInput, "text-xs")}
            />
          </label>
        ))}
      </div>
    </div>
  );

  return (
    <section className="rounded-xl bg-slate-800/30 p-4 ring-1 ring-amber-500/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-amber-100">BDI — perfil edital / TCU</h3>
          <p className="mt-1 text-xs text-slate-500">
            Fórmula TCU: ((1+AC)(1+G)(1+R)(1+DF)) / (1−L−T) − 1 · ComD e SemD separados.
          </p>
        </div>
        <div className="text-right text-xs text-slate-400">
          <div>ComD: <span className="font-mono text-cyan-300">{pct(previewRates.comd)}</span></div>
          <div>SemD: <span className="font-mono text-emerald-300">{pct(previewRates.semd)}</span></div>
        </div>
      </div>

      <label className={cn(budgetField, "mt-4 block max-w-md")}>
        <span className={budgetFieldLabel}>Perfil de BDI</span>
        <select
          value={profileId}
          disabled={disabled || saving}
          onChange={(e) => setProfileId(e.target.value)}
          className={budgetSelect}
        >
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>

      {selectedProfile?.description && (
        <p className="mt-2 text-[11px] text-slate-500">{selectedProfile.description}</p>
      )}

      {profileId === "custom_edital" && (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {renderComponentGrid("Componentes ComD", componentsComd, setComponentsComd)}
          {renderComponentGrid("Componentes SemD", componentsSemd, setComponentsSemd)}
        </div>
      )}

      {profileId !== "seminf_table" && profileId !== "custom_edital" && selectedProfile && (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {renderComponentGrid(
            "Componentes ComD (referência edital)",
            selectedProfile.components_comd,
            () => {}
          )}
          {renderComponentGrid(
            "Componentes SemD (referência edital)",
            selectedProfile.components_semd,
            () => {}
          )}
        </div>
      )}

      <button
        type="button"
        disabled={disabled || saving}
        onClick={() => void applyProfile()}
        className={cn(
          budgetBtn,
          "mt-4 bg-amber-600/20 px-4 py-2 text-sm text-amber-100 ring-amber-500/40 hover:bg-amber-600/30"
        )}
      >
        {saving ? "Aplicando BDI…" : "Aplicar perfil BDI"}
      </button>

      {validation && validation.issue_count > 0 && (
        <div
          className="mt-4 space-y-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"
          data-testid="budget-bdi-validation"
        >
          <p className="text-xs font-medium text-amber-200">
            Validação edital — {validation.status === "error" ? "revisar antes de licitar" : "atenção"}
          </p>
          <ul className="space-y-1 text-[11px] text-amber-100/90">
            {validation.issues.map((issue) => (
              <li key={issue.code}>• {issue.message}</li>
            ))}
          </ul>
        </div>
      )}

      {validation && validation.status === "ok" && (
        <p className="mt-3 text-[11px] text-emerald-400" data-testid="budget-bdi-validation-ok">
          BDI validado vs perfil edital ({validation.profile_label ?? validation.profile_id}).
        </p>
      )}
    </section>
  );
}
