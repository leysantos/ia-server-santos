"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, formatApiError } from "@/services/api";
import type { BudgetProjectInfo, BudgetSessionResponse } from "@/types/api";
import { cn } from "@/lib/utils";
import {
  budgetBtn,
  budgetField,
  budgetFieldLabel,
  budgetInput,
} from "@/lib/budget-ui";

export interface ExportBrandingConfig {
  header_title?: string;
  header_line1?: string;
  header_line2?: string;
  header_line3?: string;
  footer_line1?: string;
  footer_line2?: string;
  show_logo?: boolean;
  has_logo?: boolean;
}

interface BudgetExportBrandingPanelProps {
  sessionId: string;
  project?: BudgetProjectInfo | null;
  disabled?: boolean;
  onSessionUpdate?: (session: BudgetSessionResponse) => void;
}

function mergeBrandingWithProject(
  branding: ExportBrandingConfig,
  project?: BudgetProjectInfo | null
): ExportBrandingConfig {
  if (!project) return branding;
  const local = [project.local, project.orcamento].filter(Boolean).join(" · ");
  const footer2 = [project.processo, project.data_ref].filter(Boolean).join(" · ");
  return {
    ...branding,
    header_line1: branding.header_line1 || project.empresa || project.orgao || "",
    header_line2: branding.header_line2 || project.projeto || project.objeto || "",
    header_line3: branding.header_line3 || local,
    footer_line1: branding.footer_line1 || project.responsavel_tecnico || "",
    footer_line2: branding.footer_line2 || footer2,
  };
}

export default function BudgetExportBrandingPanel({
  sessionId,
  project,
  disabled,
  onSessionUpdate,
}: BudgetExportBrandingPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [branding, setBranding] = useState<ExportBrandingConfig>({});
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const loadBranding = useCallback(async () => {
    try {
      const data = await api.pricingExportBranding(sessionId);
      setBranding(mergeBrandingWithProject(data, project));
      if (data.has_logo) {
        setLogoPreview(api.pricingExportLogoUrl(sessionId));
      } else {
        setLogoPreview(null);
      }
    } catch {
      setBranding(mergeBrandingWithProject({}, project));
      setLogoPreview(null);
    }
  }, [sessionId, project]);

  useEffect(() => {
    void loadBranding();
  }, [loadBranding]);

  useEffect(() => {
    setBranding((prev) => mergeBrandingWithProject(prev, project));
  }, [project]);

  const patch = (field: keyof ExportBrandingConfig, value: string | boolean) => {
    setBranding((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.pricingUpdateExportBranding(sessionId, {
        header_title: branding.header_title ?? "PLANILHA ORÇAMENTÁRIA",
        header_line1: branding.header_line1 ?? "",
        header_line2: branding.header_line2 ?? "",
        header_line3: branding.header_line3 ?? "",
        footer_line1: branding.footer_line1 ?? "",
        footer_line2: branding.footer_line2 ?? "",
        show_logo: branding.show_logo ?? true,
      });
      if (res.export_branding) {
        setBranding(mergeBrandingWithProject(res.export_branding as ExportBrandingConfig, project));
      }
      if (res.session && onSessionUpdate) onSessionUpdate(res.session);
      setSaved(true);
    } catch (err) {
      setError(formatApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  };

  const handleLogoUpload = async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.pricingUploadExportLogo(sessionId, file);
      if (res.export_branding) {
        setBranding((prev) => ({
          ...mergeBrandingWithProject(res.export_branding as ExportBrandingConfig, project),
          has_logo: true,
          show_logo: true,
        }));
      } else {
        setBranding((prev) => ({ ...prev, has_logo: true, show_logo: true }));
      }
      if (res.session && onSessionUpdate) onSessionUpdate(res.session);
      setLogoPreview(api.pricingExportLogoUrl(sessionId));
    } catch (err) {
      setError(formatApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-xl bg-slate-800/30 ring-1 ring-slate-700/50">
      <div className="border-b border-slate-700/50 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-200">Personalização de exportação</h3>
        <p className="mt-0.5 text-xs text-slate-500">
          Logo, cabeçalho e rodapé usados nos PDFs e planilhas Excel gerados.
          Dados da empresa (endereço, contato, RT) vêm de{" "}
          <a href="/settings/company" className="text-cyan-400 underline hover:text-cyan-300">
            Configurações → Empresa
          </a>
          .
        </p>
      </div>

      <div className="grid gap-4 p-4 md:grid-cols-2">
        <div className="space-y-3">
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Logo da empresa</span>
            <div className="flex items-center gap-3">
              {logoPreview && branding.show_logo !== false ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={logoPreview}
                  alt="Logo"
                  className="h-12 max-w-[120px] rounded border border-slate-600 object-contain bg-white/90 p-1"
                />
              ) : (
                <div className="flex h-12 w-24 items-center justify-center rounded border border-dashed border-slate-600 text-xs text-slate-500">
                  Sem logo
                </div>
              )}
              <button
                type="button"
                disabled={disabled || loading}
                onClick={() => fileRef.current?.click()}
                className={cn(budgetBtn, "bg-slate-700/50 px-3 text-xs text-slate-300 ring-slate-600 hover:bg-slate-700")}
              >
                Enviar logo
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleLogoUpload(f);
                  if (fileRef.current) fileRef.current.value = "";
                }}
              />
            </div>
          </label>

          <label className="flex items-center gap-2 text-sm text-slate-400">
            <input
              type="checkbox"
              checked={branding.show_logo !== false}
              disabled={disabled || loading}
              onChange={(e) => patch("show_logo", e.target.checked)}
              className="rounded border-slate-600"
            />
            Exibir logo nos documentos
          </label>
        </div>

        <div className="space-y-3">
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Título do documento</span>
            <input
              type="text"
              disabled={disabled || loading}
              value={branding.header_title ?? ""}
              onChange={(e) => patch("header_title", e.target.value)}
              placeholder="PLANILHA ORÇAMENTÁRIA"
              className={budgetInput}
            />
          </label>
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Cabeçalho — linha 1 (empresa)</span>
            <input
              type="text"
              disabled={disabled || loading}
              value={branding.header_line1 ?? ""}
              onChange={(e) => patch("header_line1", e.target.value)}
              className={budgetInput}
            />
          </label>
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Cabeçalho — linha 2 (obra)</span>
            <input
              type="text"
              disabled={disabled || loading}
              value={branding.header_line2 ?? ""}
              onChange={(e) => patch("header_line2", e.target.value)}
              className={budgetInput}
            />
          </label>
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Cabeçalho — linha 3 (local / código)</span>
            <input
              type="text"
              disabled={disabled || loading}
              value={branding.header_line3 ?? ""}
              onChange={(e) => patch("header_line3", e.target.value)}
              className={budgetInput}
            />
          </label>
        </div>

        <div className="space-y-3 md:col-span-2 md:grid md:grid-cols-2 md:gap-4">
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Rodapé — linha 1 (RT / responsável)</span>
            <input
              type="text"
              disabled={disabled || loading}
              value={branding.footer_line1 ?? ""}
              onChange={(e) => patch("footer_line1", e.target.value)}
              className={budgetInput}
            />
          </label>
          <label className={budgetField}>
            <span className={budgetFieldLabel}>Rodapé — linha 2 (processo / data)</span>
            <input
              type="text"
              disabled={disabled || loading}
              value={branding.footer_line2 ?? ""}
              onChange={(e) => patch("footer_line2", e.target.value)}
              className={budgetInput}
            />
          </label>
        </div>
      </div>

      {error && (
        <p className="px-4 pb-2 text-sm text-red-400">{error}</p>
      )}

      <div className="flex items-center gap-3 border-t border-slate-700/50 px-4 py-3">
        <button
          type="button"
          disabled={disabled || loading}
          onClick={() => void handleSave()}
          className={cn(budgetBtn, "bg-cyan-600/20 px-4 text-sm text-cyan-300 ring-cyan-500/40 hover:bg-cyan-600/30")}
        >
          {loading ? "Salvando…" : "Salvar personalização"}
        </button>
        {saved && <span className="text-xs text-emerald-400">Salvo</span>}
      </div>
    </div>
  );
}
