"use client";

import NetworkAccessSettingsPanel from "@/components/NetworkAccessSettingsPanel";

export default function SettingsAccessPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-auto p-6 md:p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-100">Acesso e conectividade</h1>
        <p className="mt-1 text-sm text-slate-400">
          Rede interna do escritório e exposição externa via Cloudflare Tunnel / Access.
        </p>
      </header>
      <NetworkAccessSettingsPanel />
    </div>
  );
}
