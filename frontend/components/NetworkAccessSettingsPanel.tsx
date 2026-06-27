"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getApiBaseUrl, formatApiError } from "@/services/api";
import type { NetworkAccessConfig } from "@/types/api";
import { useAuth } from "@/context/AuthContext";
import ActionDialog from "@/components/ActionDialog";
import { cn } from "@/lib/utils";

function fieldClass() {
  return "w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30";
}

function labelClass() {
  return "mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500";
}

async function copyText(text: string): Promise<boolean> {
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function modeBadgeClass(mode: string) {
  if (mode.startsWith("quick-tunnel")) return "bg-amber-500/20 text-amber-200";
  if (mode === "cloudflare") return "bg-orange-500/20 text-orange-200";
  if (mode === "hybrid") return "bg-violet-500/20 text-violet-200";
  return "bg-emerald-500/20 text-emerald-200";
}

function SectionToggle({
  enabled,
  onChange,
  label,
  description,
}: {
  enabled: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-white/10 bg-slate-950/40 p-4">
      <input
        type="checkbox"
        checked={enabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1"
      />
      <span>
        <span className="block text-sm font-medium text-slate-100">{label}</span>
        <span className="mt-0.5 block text-xs text-slate-400">{description}</span>
      </span>
    </label>
  );
}

export default function NetworkAccessSettingsPanel() {
  const { isAdmin } = useAuth();
  const [config, setConfig] = useState<NetworkAccessConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tunnelToken, setTunnelToken] = useState("");
  const [corsText, setCorsText] = useState("");
  const [tunnelBusy, setTunnelBusy] = useState(false);
  const [dialog, setDialog] = useState({ open: false, title: "", message: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.systemNetworkAccess();
      setConfig(data);
      setCorsText((data.cors_extra_origins || []).join("\n"));
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

  const patchInternal = (key: keyof NetworkAccessConfig["internal"], value: string | number | boolean) => {
    setConfig((prev) =>
      prev
        ? {
            ...prev,
            internal: { ...prev.internal, [key]: value },
          }
        : prev
    );
  };

  const patchCloudflare = (
    key: keyof NetworkAccessConfig["cloudflare"],
    value: string | number | boolean
  ) => {
    setConfig((prev) =>
      prev
        ? {
            ...prev,
            cloudflare: { ...prev.cloudflare, [key]: value },
          }
        : prev
    );
  };

  const handleSave = async () => {
    if (!config || !isAdmin) return;
    setSaving(true);
    try {
      const cors_extra_origins = corsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const body: Parameters<typeof api.systemUpdateNetworkAccess>[0] = {
        internal: config.internal,
        cloudflare: { ...config.cloudflare },
        cors_extra_origins,
      };
      if (tunnelToken.trim()) {
        body.cloudflare!.tunnel_token = tunnelToken.trim();
      }
      const saved = await api.systemUpdateNetworkAccess(body);
      setConfig(saved);
      setTunnelToken("");
      setDialog({
        open: true,
        title: "Configuração salva",
        message: saved.restart_hint || "Configurações de acesso atualizadas.",
      });
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

  const handleStartQuickTunnel = async () => {
    if (!isAdmin) return;
    setTunnelBusy(true);
    try {
      const result = await api.systemStartQuickTunnel();
      await load();
      setDialog({
        open: true,
        title: "Túnel temporário iniciado",
        message: [
          result.message || "URLs públicas geradas.",
          result.frontend_url ? `Frontend: ${result.frontend_url}` : "",
          result.api_url ? `API: ${result.api_url}` : "",
          result.restart_hint || "",
          result.env_hint ? result.env_hint : "",
        ]
          .filter(Boolean)
          .join("\n\n"),
      });
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao iniciar túnel",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setTunnelBusy(false);
    }
  };

  const handleStopQuickTunnel = async () => {
    if (!isAdmin) return;
    setTunnelBusy(true);
    try {
      const result = await api.systemStopQuickTunnel();
      await load();
      setDialog({
        open: true,
        title: "Túnel encerrado",
        message: result.message || "O acesso temporário via trycloudflare foi desligado.",
      });
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao parar túnel",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setTunnelBusy(false);
    }
  };

  const handleCopy = async (label: string, value: string) => {
    const ok = await copyText(value);
    setDialog({
      open: true,
      title: ok ? "Copiado" : "Não foi possível copiar",
      message: ok ? `${label} copiado para a área de transferência.` : value,
    });
  };

  if (loading || !config) {
    return <p className="text-sm text-slate-400">Carregando configurações de rede…</p>;
  }

  const mode = config.effective_access_mode || "local";
  const qt = config.quick_tunnel;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
        <span className="text-sm text-slate-300">Modo de acesso atual:</span>
        <span
          className={cn(
            "rounded-full px-3 py-1 text-xs font-medium uppercase tracking-wide",
            modeBadgeClass(mode)
          )}
        >
          {mode}
        </span>
        <span className="text-xs text-slate-500">API em uso: {getApiBaseUrl()}</span>
      </div>

      {!isAdmin ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          Visualização somente leitura. Apenas administradores podem alterar as configurações de acesso.
        </div>
      ) : null}

      <section className="space-y-4 rounded-xl border border-white/10 bg-slate-900/40 p-6">
        <h2 className="text-lg font-medium text-slate-100">Rede interna (escritório / LAN)</h2>
        <p className="text-sm text-slate-400">
          Configure URLs e faixas IP para acesso na rede local da empresa (WSL, servidor interno, VLAN).
        </p>

        <SectionToggle
          enabled={config.internal.enabled}
          onChange={(v) => patchInternal("enabled", v)}
          label="Habilitar acesso na rede interna"
          description="Permite que colegas na mesma rede acessem o frontend e a API pelos endereços abaixo."
        />

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className={labelClass()}>IP do host (servidor)</label>
            <input
              value={config.internal.host_ip}
              onChange={(e) => patchInternal("host_ip", e.target.value)}
              placeholder="192.168.1.50"
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass()}>Porta API</label>
              <input
                type="number"
                value={config.internal.api_port}
                onChange={(e) => patchInternal("api_port", Number(e.target.value))}
                className={fieldClass()}
                disabled={!isAdmin}
              />
            </div>
            <div>
              <label className={labelClass()}>Porta frontend</label>
              <input
                type="number"
                value={config.internal.frontend_port}
                onChange={(e) => patchInternal("frontend_port", Number(e.target.value))}
                className={fieldClass()}
                disabled={!isAdmin}
              />
            </div>
          </div>
          <div>
            <label className={labelClass()}>URL da API</label>
            <input
              value={config.internal.api_base_url}
              onChange={(e) => patchInternal("api_base_url", e.target.value)}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>URL do frontend</label>
            <input
              value={config.internal.frontend_url}
              onChange={(e) => patchInternal("frontend_url", e.target.value)}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div className="md:col-span-2">
            <label className={labelClass()}>CIDRs permitidos (um por linha)</label>
            <textarea
              value={config.internal.allowed_cidrs.join("\n")}
              onChange={(e) =>
                setConfig((prev) =>
                  prev
                    ? {
                        ...prev,
                        internal: {
                          ...prev.internal,
                          allowed_cidrs: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                        },
                      }
                    : prev
                )
              }
              rows={3}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div className="md:col-span-2">
            <label className={labelClass()}>Observações</label>
            <textarea
              value={config.internal.notes}
              onChange={(e) => patchInternal("notes", e.target.value)}
              rows={2}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-xl border border-amber-500/25 bg-amber-500/5 p-6">
        <h2 className="text-lg font-medium text-slate-100">Acesso temporário — Quick Tunnel</h2>
        <p className="text-sm text-slate-400">
          Exponha o sistema na internet sem domínio próprio usando URLs{" "}
          <span className="font-mono text-amber-200/90">*.trycloudflare.com</span>. Ideal para
          demonstrações rápidas com a equipe. As URLs mudam a cada reinício do túnel.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <span
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium uppercase tracking-wide",
              qt?.running ? "bg-emerald-500/20 text-emerald-200" : "bg-slate-700/50 text-slate-300"
            )}
          >
            {qt?.running ? "Túnel ativo" : "Túnel parado"}
          </span>
          {qt?.cloudflared_installed === false ? (
            <span className="text-xs text-rose-300">cloudflared não instalado no servidor</span>
          ) : null}
          {qt?.started_at ? (
            <span className="text-xs text-slate-500">Iniciado em {qt.started_at}</span>
          ) : null}
        </div>

        {(qt?.api_url || qt?.frontend_url) && qt?.running ? (
          <div className="grid gap-3 md:grid-cols-2">
            {qt.frontend_url ? (
              <div className="rounded-lg border border-white/10 bg-slate-950/50 p-3">
                <p className={labelClass()}>URL do frontend</p>
                <div className="flex items-center gap-2">
                  <a
                    href={qt.frontend_url}
                    target="_blank"
                    rel="noreferrer"
                    className="min-w-0 flex-1 truncate font-mono text-xs text-cyan-300 hover:underline"
                  >
                    {qt.frontend_url}
                  </a>
                  <button
                    type="button"
                    onClick={() => void handleCopy("URL do frontend", qt.frontend_url)}
                    className="shrink-0 rounded border border-white/10 px-2 py-1 text-[11px] text-slate-300 hover:bg-white/5"
                  >
                    Copiar
                  </button>
                </div>
              </div>
            ) : null}
            {qt.api_url ? (
              <div className="rounded-lg border border-white/10 bg-slate-950/50 p-3">
                <p className={labelClass()}>URL da API</p>
                <div className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-300">
                    {qt.api_url}
                  </span>
                  <button
                    type="button"
                    onClick={() => void handleCopy("URL da API", qt.api_url)}
                    className="shrink-0 rounded border border-white/10 px-2 py-1 text-[11px] text-slate-300 hover:bg-white/5"
                  >
                    Copiar
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {qt?.env_hint ? (
          <div className="rounded-lg border border-white/5 bg-slate-950/50 p-4 text-xs text-slate-400">
            <p className="font-medium text-slate-300">Após iniciar o túnel</p>
            <p className="mt-2">{qt.restart_hint}</p>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all font-mono text-[11px] text-amber-200/90">
              {qt.env_hint}
            </pre>
            <p className="mt-2">
              Reinicie o frontend (<code className="text-slate-300">npm run dev</code>) para aplicar o proxy{" "}
              <code className="text-slate-300">/api-backend</code>.
            </p>
          </div>
        ) : (
          <div className="rounded-lg border border-white/5 bg-slate-950/50 p-4 text-xs text-slate-400">
            <p>
              Certifique-se de que a API (<code className="text-slate-300">:8000</code>) e o frontend (
              <code className="text-slate-300">:3000</code>) já estão rodando antes de iniciar.
            </p>
          </div>
        )}

        {isAdmin ? (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={tunnelBusy || qt?.cloudflared_installed === false || qt?.running}
              onClick={() => void handleStartQuickTunnel()}
              className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50"
            >
              {tunnelBusy ? "Processando…" : "Iniciar túnel temporário"}
            </button>
            <button
              type="button"
              disabled={tunnelBusy || !qt?.running}
              onClick={() => void handleStopQuickTunnel()}
              className="rounded-lg border border-white/15 px-4 py-2 text-sm text-slate-200 hover:bg-white/5 disabled:opacity-50"
            >
              Parar túnel
            </button>
          </div>
        ) : null}
      </section>

      <section className="space-y-4 rounded-xl border border-white/10 bg-slate-900/40 p-6">
        <h2 className="text-lg font-medium text-slate-100">Acesso externo — Cloudflare Tunnel</h2>
        <p className="text-sm text-slate-400">
          Exponha o sistema com segurança via Cloudflare Tunnel e Cloudflare Access (Zero Trust).
        </p>

        <SectionToggle
          enabled={config.cloudflare.enabled}
          onChange={(v) => patchCloudflare("enabled", v)}
          label="Habilitar túnel Cloudflare"
          description="Use hostname público com política de acesso Cloudflare Access."
        />

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className={labelClass()}>Nome do túnel</label>
            <input
              value={config.cloudflare.tunnel_name}
              onChange={(e) => patchCloudflare("tunnel_name", e.target.value)}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>Tunnel ID</label>
            <input
              value={config.cloudflare.tunnel_id}
              onChange={(e) => patchCloudflare("tunnel_id", e.target.value)}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div className="md:col-span-2">
            <label className={labelClass()}>
              Token do túnel
              {config.cloudflare.tunnel_token_configured ? (
                <span className="ml-2 normal-case text-emerald-400">
                  (configurado {config.cloudflare.tunnel_token_hint || ""})
                </span>
              ) : null}
            </label>
            <input
              type="password"
              value={tunnelToken}
              onChange={(e) => setTunnelToken(e.target.value)}
              placeholder={config.cloudflare.tunnel_token_configured ? "Deixe em branco para manter" : "Cole o token do cloudflared"}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>Hostname público</label>
            <input
              value={config.cloudflare.public_hostname}
              onChange={(e) => patchCloudflare("public_hostname", e.target.value)}
              placeholder="ia.suaempresa.com"
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>URL pública da API</label>
            <input
              value={config.cloudflare.public_api_url}
              onChange={(e) => patchCloudflare("public_api_url", e.target.value)}
              placeholder="https://api-ia.suaempresa.com"
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>URL pública do frontend</label>
            <input
              value={config.cloudflare.public_frontend_url}
              onChange={(e) => patchCloudflare("public_frontend_url", e.target.value)}
              placeholder="https://ia.suaempresa.com"
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>Cloudflare Account ID</label>
            <input
              value={config.cloudflare.account_id}
              onChange={(e) => patchCloudflare("account_id", e.target.value)}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>Zone ID</label>
            <input
              value={config.cloudflare.zone_id}
              onChange={(e) => patchCloudflare("zone_id", e.target.value)}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>Aplicação Access</label>
            <input
              value={config.cloudflare.access_application_name}
              onChange={(e) => patchCloudflare("access_application_name", e.target.value)}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className={labelClass()}>Política Access</label>
            <input
              value={config.cloudflare.access_policy}
              onChange={(e) => patchCloudflare("access_policy", e.target.value)}
              placeholder="E-mail corporativo, grupo, etc."
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
          <div className="md:col-span-2">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={config.cloudflare.warp_required}
                onChange={(e) => patchCloudflare("warp_required", e.target.checked)}
                disabled={!isAdmin}
              />
              Exigir Cloudflare WARP para acesso externo
            </label>
          </div>
          <div className="md:col-span-2">
            <label className={labelClass()}>Observações Cloudflare</label>
            <textarea
              value={config.cloudflare.notes}
              onChange={(e) => patchCloudflare("notes", e.target.value)}
              rows={2}
              className={fieldClass()}
              disabled={!isAdmin}
            />
          </div>
        </div>

        <div className="rounded-lg border border-white/5 bg-slate-950/50 p-4 text-xs text-slate-400">
          <p className="font-medium text-slate-300">Comando cloudflared (referência)</p>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all font-mono text-[11px] text-slate-500">
            {`cloudflared tunnel run ${config.cloudflare.tunnel_name || "<tunnel-name>"}`}
          </pre>
        </div>
      </section>

      <section className="space-y-4 rounded-xl border border-white/10 bg-slate-900/40 p-6">
        <h2 className="text-lg font-medium text-slate-100">CORS e origens sugeridas</h2>
        <p className="text-sm text-slate-400">
          Origens extras para o middleware CORS da API. Após salvar, reinicie a API se adicionar domínios novos no
          `.env`.
        </p>
        <div>
          <label className={labelClass()}>Origens extras (uma por linha)</label>
          <textarea
            value={corsText}
            onChange={(e) => setCorsText(e.target.value)}
            rows={3}
            className={fieldClass()}
            disabled={!isAdmin}
          />
        </div>
        <div>
          <label className={labelClass()}>Origens sugeridas (efetivas)</label>
          <ul className="mt-1 space-y-1 text-xs text-slate-400">
            {(config.suggested_cors_origins || []).map((origin) => (
              <li key={origin} className="font-mono">
                {origin}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {isAdmin ? (
        <button
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
          className="rounded-lg bg-cyan-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-60"
        >
          {saving ? "Salvando…" : "Salvar configurações de acesso"}
        </button>
      ) : null}

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
      />
    </div>
  );
}
