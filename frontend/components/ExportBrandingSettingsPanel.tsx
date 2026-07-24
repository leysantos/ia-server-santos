"use client";

import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/services/api";
import type { ExportBrandingConfig } from "@/types/api";
import { cn } from "@/lib/utils";

function fieldClass() {
  return "w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30";
}

function labelClass() {
  return "mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500";
}

interface ExportBrandingSettingsPanelProps {
  /** Indica se há logo cadastrada no servidor (não usar URL direta — endpoints exigem JWT). */
  hasLogo: boolean;
  hasBrasao: boolean;
  /** Incrementar após upload para forçar recarregar o blob autenticado. */
  assetRev?: number;
  onUploadLogo: (file: File) => Promise<void>;
  onUploadBrasao: (file: File) => Promise<void>;
  disabled?: boolean;
}

function useAuthImagePreview(enabled: boolean, fetchBlob: () => Promise<Blob>, rev: number) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    if (!enabled) {
      setPreviewUrl((prev) => {
        if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
        return null;
      });
      setLoading(false);
      return;
    }

    setLoading(true);
    fetchBlob()
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl((prev) => {
          if (prev?.startsWith("blob:") && prev !== objectUrl) URL.revokeObjectURL(prev);
          return objectUrl;
        });
      })
      .catch(() => {
        // Mantém preview local (se houver) em caso de falha da API
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, fetchBlob, rev]);

  const setLocalPreview = useCallback((file: File) => {
    const localUrl = URL.createObjectURL(file);
    setPreviewUrl((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return localUrl;
    });
  }, []);

  return { previewUrl, loading, setLocalPreview };
}

export default function ExportBrandingSettingsPanel({
  hasLogo,
  hasBrasao,
  assetRev = 0,
  onUploadLogo,
  onUploadBrasao,
  disabled,
}: ExportBrandingSettingsPanelProps) {
  const [branding, setBranding] = useState<ExportBrandingConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLogo = useCallback(() => api.systemFetchCompanyLogo(), []);
  const fetchBrasao = useCallback(() => api.systemFetchCompanyBrasao(), []);

  const {
    previewUrl: logoPreview,
    loading: logoLoading,
    setLocalPreview: setLocalLogo,
  } = useAuthImagePreview(hasLogo, fetchLogo, assetRev);
  const {
    previewUrl: brasaoPreview,
    loading: brasaoLoading,
    setLocalPreview: setLocalBrasao,
  } = useAuthImagePreview(hasBrasao, fetchBrasao, assetRev);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.systemExportBranding();
      setBranding(data);
    } catch (err) {
      setError(formatApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const patch = (field: keyof ExportBrandingConfig, value: string | boolean) => {
    setBranding((prev) => (prev ? { ...prev, [field]: value } : prev));
    setSaved(false);
  };

  const handleSave = async () => {
    if (!branding) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.systemUpdateExportBranding({
        header_title: branding.header_title ?? "PLANILHA ORÇAMENTÁRIA",
        header_line1: branding.header_line1 ?? "",
        header_line2: branding.header_line2 ?? "",
        header_line3: branding.header_line3 ?? "",
        footer_line1: branding.footer_line1 ?? "",
        footer_line2: branding.footer_line2 ?? "",
        show_logo: branding.show_logo ?? true,
        show_brasao: branding.show_brasao ?? true,
      });
      setBranding(updated);
      setSaved(true);
    } catch (err) {
      setError(formatApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setSaving(false);
    }
  };

  if (loading || !branding) {
    return (
      <div className="rounded-xl bg-slate-900/40 p-6 text-sm text-slate-500 ring-1 ring-slate-800">
        Carregando personalização de exportação…
      </div>
    );
  }

  const showLogoSlot = branding.show_logo !== false;
  const logoSrc = showLogoSlot ? logoPreview : null;
  const brasaoSrc = brasaoPreview;

  return (
    <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
      <h3 className="text-base font-semibold text-white">Personalização de exportação (PDF e Excel)</h3>
      <p className="mt-1 text-sm text-slate-500">
        Cabeçalho e rodapé aplicados a <strong className="font-medium text-slate-400">todos os orçamentos</strong>.
        Endereço e contato da empresa vêm do cadastro acima; linhas de rodapé abaixo complementam RT e processo.
      </p>

      <div className="mt-4 grid gap-6 md:grid-cols-2">
        <div className="space-y-4">
          <div>
            <p className={labelClass()}>Logo (cabeçalho — canto esquerdo)</p>
            <div className="flex items-center gap-3">
              {logoSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={logoSrc}
                  alt="Logo"
                  className="h-12 max-w-[120px] rounded border border-slate-600 bg-white/90 p-1 object-contain"
                />
              ) : (
                <div className="flex h-12 w-24 items-center justify-center rounded border border-dashed border-slate-600 text-xs text-slate-500">
                  {logoLoading ? "…" : "Sem logo"}
                </div>
              )}
              <label className="cursor-pointer rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700">
                Importar logo
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  disabled={disabled || saving}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setLocalLogo(f);
                      void onUploadLogo(f);
                    }
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
            <label className="mt-2 flex items-center gap-2 text-sm text-slate-400">
              <input
                type="checkbox"
                checked={branding.show_logo !== false}
                disabled={disabled || saving}
                onChange={(e) => patch("show_logo", e.target.checked)}
                className="rounded border-slate-600"
              />
              Exibir logo nos documentos
            </label>
          </div>

          <div>
            <p className={labelClass()}>Brasão (corpo da página — centralizado)</p>
            <div className="flex items-center gap-3">
              {brasaoSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={brasaoSrc}
                  alt="Brasão"
                  className="h-12 max-w-[120px] rounded border border-slate-600 bg-white/90 p-1 object-contain"
                />
              ) : (
                <div className="flex h-12 w-24 items-center justify-center rounded border border-dashed border-slate-600 text-xs text-slate-500">
                  {brasaoLoading ? "…" : "Sem brasão"}
                </div>
              )}
              <label className="cursor-pointer rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700">
                Importar brasão
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  disabled={disabled || saving}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setLocalBrasao(f);
                      void onUploadBrasao(f);
                    }
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
            <label className="mt-2 flex items-center gap-2 text-sm text-slate-400">
              <input
                type="checkbox"
                checked={branding.show_brasao !== false}
                disabled={disabled || saving}
                onChange={(e) => patch("show_brasao", e.target.checked)}
                className="rounded border-slate-600"
              />
              Exibir brasão centralizado no corpo das páginas
            </label>
          </div>
        </div>

        <div className="space-y-3">
          <label>
            <span className={labelClass()}>Título do documento</span>
            <input
              type="text"
              disabled={disabled || saving}
              value={branding.header_title ?? ""}
              onChange={(e) => patch("header_title", e.target.value)}
              placeholder="PLANILHA ORÇAMENTÁRIA"
              className={fieldClass()}
            />
          </label>
          <label>
            <span className={labelClass()}>Cabeçalho — linha 1 (empresa)</span>
            <input
              type="text"
              disabled={disabled || saving}
              value={branding.header_line1 ?? ""}
              onChange={(e) => patch("header_line1", e.target.value)}
              className={fieldClass()}
            />
          </label>
          <label>
            <span className={labelClass()}>Cabeçalho — linha 2</span>
            <input
              type="text"
              disabled={disabled || saving}
              value={branding.header_line2 ?? ""}
              onChange={(e) => patch("header_line2", e.target.value)}
              className={fieldClass()}
            />
          </label>
          <label>
            <span className={labelClass()}>Cabeçalho — linha 3 (CNPJ / local)</span>
            <input
              type="text"
              disabled={disabled || saving}
              value={branding.header_line3 ?? ""}
              onChange={(e) => patch("header_line3", e.target.value)}
              className={fieldClass()}
            />
          </label>
        </div>

        <div className="space-y-3 md:col-span-2 md:grid md:grid-cols-2 md:gap-4">
          <label>
            <span className={labelClass()}>Rodapé — linha 1 (RT / responsável)</span>
            <input
              type="text"
              disabled={disabled || saving}
              value={branding.footer_line1 ?? ""}
              onChange={(e) => patch("footer_line1", e.target.value)}
              className={fieldClass()}
            />
          </label>
          <label>
            <span className={labelClass()}>Rodapé — linha 2 (processo / contato)</span>
            <input
              type="text"
              disabled={disabled || saving}
              value={branding.footer_line2 ?? ""}
              onChange={(e) => patch("footer_line2", e.target.value)}
              className={fieldClass()}
            />
          </label>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          disabled={disabled || saving}
          onClick={() => void handleSave()}
          className={cn(
            "rounded-xl px-5 py-2 text-sm font-medium ring-1 transition",
            saving
              ? "cursor-not-allowed bg-slate-800 text-slate-500 ring-slate-700"
              : "bg-cyan-600/20 text-cyan-200 ring-cyan-500/40 hover:bg-cyan-600/30"
          )}
        >
          {saving ? "Salvando…" : "Salvar personalização"}
        </button>
        {saved && <span className="text-xs text-emerald-400">Salvo</span>}
      </div>
    </section>
  );
}
