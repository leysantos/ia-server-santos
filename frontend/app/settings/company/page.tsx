"use client";

import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/services/api";
import type { CompanyProfile } from "@/types/api";
import { cn } from "@/lib/utils";
import ActionDialog from "@/components/ActionDialog";
import ExportBrandingSettingsPanel from "@/components/ExportBrandingSettingsPanel";

const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
  "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

function fieldClass() {
  return "w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30";
}

function labelClass() {
  return "mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500";
}

export default function SettingsCompanyPage() {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState<{ open: boolean; title: string; message: string }>({
    open: false,
    title: "",
    message: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.systemCompanyProfile();
      setProfile(data);
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao carregar",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const patch = (key: keyof CompanyProfile, value: string) => {
    setProfile((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const handleSave = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      const updated = await api.systemUpdateCompanyProfile({
        razao_social: profile.razao_social,
        nome_fantasia: profile.nome_fantasia,
        cnpj: profile.cnpj,
        endereco: profile.endereco,
        numero: profile.numero,
        complemento: profile.complemento,
        bairro: profile.bairro,
        cidade: profile.cidade,
        uf: profile.uf,
        cep: profile.cep,
        telefone: profile.telefone,
        email: profile.email,
        site: profile.site,
        responsavel_tecnico: profile.responsavel_tecnico,
        rt_profissao: profile.rt_profissao,
        rt_crea: profile.rt_crea,
        rt_email: profile.rt_email,
        rt_telefone: profile.rt_telefone,
      });
      setProfile(updated);
      setDialog({ open: true, title: "Salvo", message: "Dados da empresa atualizados." });
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao salvar",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setSaving(false);
    }
  };

  const uploadImage = async (kind: "logo" | "brasao", file: File) => {
    setSaving(true);
    try {
      const updated =
        kind === "logo"
          ? await api.systemUploadCompanyLogo(file)
          : await api.systemUploadCompanyBrasao(file);
      setProfile(updated);
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro no upload",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading || !profile) {
    return (
      <div className="rounded-xl bg-slate-900/40 p-8 text-center text-sm text-slate-500 ring-1 ring-slate-800">
        Carregando cadastro da empresa…
      </div>
    );
  }

  const logoUrl = profile.has_logo ? api.systemCompanyLogoUrl() : null;
  const brasaoUrl = profile.has_brasao ? api.systemCompanyBrasaoUrl() : null;

  return (
    <div className="space-y-6">
      <ExportBrandingSettingsPanel
        logoUrl={logoUrl}
        brasaoUrl={brasaoUrl}
        disabled={saving}
        onUploadLogo={(file) => uploadImage("logo", file)}
        onUploadBrasao={(file) => uploadImage("brasao", file)}
      />

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h3 className="text-base font-semibold text-white">Dados da empresa</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label>
            <span className={labelClass()}>Razão social</span>
            <input className={fieldClass()} value={profile.razao_social} onChange={(e) => patch("razao_social", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Nome fantasia</span>
            <input className={fieldClass()} value={profile.nome_fantasia} onChange={(e) => patch("nome_fantasia", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>CNPJ</span>
            <input className={fieldClass()} value={profile.cnpj} onChange={(e) => patch("cnpj", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Telefone</span>
            <input className={fieldClass()} value={profile.telefone} onChange={(e) => patch("telefone", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>E-mail</span>
            <input className={fieldClass()} type="email" value={profile.email} onChange={(e) => patch("email", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Site</span>
            <input className={fieldClass()} value={profile.site} onChange={(e) => patch("site", e.target.value)} />
          </label>
        </div>
      </section>

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h3 className="text-base font-semibold text-white">Endereço</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="md:col-span-2">
            <span className={labelClass()}>Logradouro</span>
            <input className={fieldClass()} value={profile.endereco} onChange={(e) => patch("endereco", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Número</span>
            <input className={fieldClass()} value={profile.numero} onChange={(e) => patch("numero", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Complemento</span>
            <input className={fieldClass()} value={profile.complemento} onChange={(e) => patch("complemento", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Bairro</span>
            <input className={fieldClass()} value={profile.bairro} onChange={(e) => patch("bairro", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Cidade</span>
            <input className={fieldClass()} value={profile.cidade} onChange={(e) => patch("cidade", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>UF</span>
            <select className={fieldClass()} value={profile.uf} onChange={(e) => patch("uf", e.target.value)}>
              <option value="">—</option>
              {UFS.map((uf) => (
                <option key={uf} value={uf}>{uf}</option>
              ))}
            </select>
          </label>
          <label>
            <span className={labelClass()}>CEP</span>
            <input className={fieldClass()} value={profile.cep} onChange={(e) => patch("cep", e.target.value)} />
          </label>
        </div>
      </section>

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h3 className="text-base font-semibold text-white">Responsável técnico</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="md:col-span-2">
            <span className={labelClass()}>Nome completo</span>
            <input className={fieldClass()} value={profile.responsavel_tecnico} onChange={(e) => patch("responsavel_tecnico", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Profissão / título</span>
            <input className={fieldClass()} placeholder="Ex.: Eng. Civil" value={profile.rt_profissao} onChange={(e) => patch("rt_profissao", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>CREA / CAU / registro</span>
            <input className={fieldClass()} placeholder="Ex.: 31.410-AM" value={profile.rt_crea} onChange={(e) => patch("rt_crea", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>E-mail do RT</span>
            <input className={fieldClass()} type="email" value={profile.rt_email} onChange={(e) => patch("rt_email", e.target.value)} />
          </label>
          <label>
            <span className={labelClass()}>Telefone do RT</span>
            <input className={fieldClass()} value={profile.rt_telefone} onChange={(e) => patch("rt_telefone", e.target.value)} />
          </label>
        </div>
      </section>

      <div className="flex justify-end">
        <button
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
          className={cn(
            "rounded-xl px-6 py-2.5 text-sm font-medium ring-1 transition",
            saving
              ? "cursor-not-allowed bg-slate-800 text-slate-500 ring-slate-700"
              : "bg-cyan-600/20 text-cyan-200 ring-cyan-500/40 hover:bg-cyan-600/30"
          )}
        >
          {saving ? "Salvando…" : "Salvar cadastro"}
        </button>
      </div>

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        variant="info"
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
      />
    </div>
  );
}
