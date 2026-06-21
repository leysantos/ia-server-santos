"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/services/api";
import type {
  MaintenanceBackupManifest,
  MaintenanceConfigResponse,
  MaintenanceRestoreInspectResponse,
  MaintenanceStatusResponse,
} from "@/types/api";
import { cn } from "@/lib/utils";

const BACKUP_TARGETS = [
  {
    id: "app",
    label: "Aplicação",
    description: "Frontend, backend, docs, infra, scripts e Makefile (sem node_modules/.venv)",
  },
  {
    id: "database",
    label: "PostgreSQL",
    description: "Dump compactado do banco ia_server_santos",
  },
  {
    id: "knowledge",
    label: "Knowledge",
    description: "Catálogo JSONL e sidecars .knowledge.json (PDFs opcionais)",
  },
  {
    id: "faiss",
    label: "Índices FAISS",
    description: "Vetores em memory/faiss_index/",
  },
  {
    id: "config",
    label: "Config",
    description: "Exporta configuração de manutenção",
  },
] as const;

const RESTORE_TARGETS = [
  { id: "database", label: "PostgreSQL" },
  { id: "knowledge", label: "Knowledge" },
  { id: "faiss", label: "FAISS" },
  { id: "app", label: "Código (app)" },
] as const;

export default function SettingsMaintenancePage() {
  const [status, setStatus] = useState<MaintenanceStatusResponse | null>(null);
  const [config, setConfig] = useState<MaintenanceConfigResponse | null>(null);
  const [selected, setSelected] = useState<string[]>(["app", "database", "knowledge", "faiss"]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<MaintenanceBackupManifest | null>(null);
  const [restoreStamp, setRestoreStamp] = useState("");
  const [restoreTargets, setRestoreTargets] = useState<string[]>(["database", "knowledge", "faiss"]);
  const [availableStamps, setAvailableStamps] = useState<string[]>([]);
  const [restoreInspect, setRestoreInspect] = useState<MaintenanceRestoreInspectResponse | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [st, cfg, stampsResp] = await Promise.all([
        api.maintenanceStatus(),
        api.maintenanceConfig(),
        api.maintenanceStamps(),
      ]);
      setStatus(st);
      setConfig(cfg);
      setAvailableStamps(stampsResp.stamps);
      if (!restoreStamp && stampsResp.stamps.length) {
        setRestoreStamp(stampsResp.stamps[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar manutenção");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const toggleTarget = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id],
    );
  };

  const saveConfig = async () => {
    if (!config) return;
    setBusy("config");
    setError(null);
    setMessage(null);
    try {
      const updated = await api.maintenanceUpdateConfig({
        backup_drive_win: config.backup_drive_win,
        backup_staging_dir: config.backup_staging_dir,
        keep_latest_sets: config.keep_latest_sets,
        include_knowledge_pdfs: config.include_knowledge_pdfs,
        include_faiss: config.include_faiss,
        include_database: config.include_database,
      });
      setConfig(updated);
      setMessage("Configuração salva.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setBusy(null);
    }
  };

  const initFolders = async () => {
    setBusy("init");
    setError(null);
    setMessage(null);
    try {
      const result = await api.maintenanceInitFolders();
      setMessage(
        result.created.length
          ? `Pastas criadas: ${result.created.length}`
          : "Estrutura de pastas já existia.",
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar pastas");
    } finally {
      setBusy(null);
    }
  };

  const runBackup = async () => {
    if (!selected.length) {
      setError("Selecione ao menos um alvo de backup.");
      return;
    }
    setBusy("backup");
    setError(null);
    setMessage(null);
    try {
      const result = await api.maintenanceBackup(selected);
      setLastResult(result);
      setMessage(
        result.status === "completed"
          ? `Backup concluído — ${result.artifacts.length} artefato(s).`
          : `Backup parcial — ${result.artifacts.length} ok, ${result.errors.length} erro(s).`,
      );
      if (result.errors?.length) {
        setError(result.errors.map((e) => `${e.target}: ${e.error}`).join(" · "));
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no backup");
    } finally {
      setBusy(null);
    }
  };

  const inspectRestore = async () => {
    if (!restoreStamp.trim()) return;
    setBusy("inspect");
    setError(null);
    try {
      const info = await api.maintenanceRestoreInspect(restoreStamp.trim());
      setRestoreInspect(info);
      setMessage(`Stamp ${restoreStamp}: ${Object.keys(info.artifacts).length} artefato(s) disponível(is).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao inspecionar stamp");
    } finally {
      setBusy(null);
    }
  };

  const runRestore = async (dryRun: boolean) => {
    if (!restoreStamp.trim() || !restoreTargets.length) {
      setError("Informe stamp e ao menos um alvo de restore.");
      return;
    }
    if (!dryRun) {
      const ok = window.confirm(
        `Restaurar stamp ${restoreStamp}?\n\nAlvos: ${restoreTargets.join(", ")}\n\n` +
          "O banco será recriado do zero. Knowledge e FAISS serão sobrescritos.",
      );
      if (!ok) return;
    }
    setBusy(dryRun ? "restore-dry" : "restore");
    setError(null);
    setMessage(null);
    try {
      const result = await api.maintenanceRestore({
        stamp: restoreStamp.trim(),
        targets: restoreTargets,
        from_drive: true,
        dry_run: dryRun,
      });
      setMessage(
        dryRun
          ? `Simulação OK — ${result.steps.length} passo(s).`
          : `Restore ${result.status} — ${result.steps.length} passo(s).`,
      );
      if (result.errors?.length) {
        setError(result.errors.map((e) => `${e.target}: ${e.error}`).join(" · "));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no restore");
    } finally {
      setBusy(null);
    }
  };

  const toggleRestoreTarget = (id: string) => {
    setRestoreTargets((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id],
    );
  };

  if (loading && !config) {
    return <p className="text-sm text-slate-500">Carregando manutenção…</p>;
  }

  const subfolders = config?.subfolders ?? {};

  return (
    <div className="space-y-6">
      {status?.environment && (
        <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
          <h3 className="mb-3 text-sm font-semibold text-white">Ambiente</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <Stat label="WSL" value={status.environment.is_wsl ? "Sim" : "Não"} />
            <Stat label="Repositório" value={status.environment.repo_root.split("/").slice(-2).join("/")} />
          </div>
        </section>
      )}

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h3 className="mb-1 text-sm font-semibold text-white">Google Drive e retenção</h3>
        <p className="mb-4 text-sm text-slate-500">
          Backups da aplicação são gerados em staging local e enviados ao{" "}
          <code className="text-cyan-400/90">Google Drive</code>. Mantém apenas os{" "}
          <strong className="font-medium text-slate-400">N conjuntos mais recentes</strong> — os
          antigos são apagados automaticamente (app, banco, FAISS, knowledge).
        </p>

        {config && (
          <div className="grid gap-3">
            <Field
              label="Google Drive — destino (Windows)"
              value={config.backup_drive_win}
              onChange={(v) => setConfig({ ...config, backup_drive_win: v })}
              hint="Ex.: G:\Meu Drive\Backups_IA_Server"
            />
            <Field
              label="Staging local (WSL)"
              value={config.backup_staging_dir}
              onChange={(v) => setConfig({ ...config, backup_staging_dir: v })}
              hint="Temporário no disco C: antes de enviar ao Drive"
            />
            <Field
              label="Manter últimos N conjuntos"
              value={String(config.keep_latest_sets ?? 1)}
              onChange={(v) => {
                const n = parseInt(v, 10);
                if (!Number.isNaN(n) && n >= 1 && n <= 10) {
                  setConfig({ ...config, keep_latest_sets: n });
                }
              }}
              hint="1 = só o backup mais recente (~1 GB app + FAISS + banco)"
            />
            <div className="flex flex-wrap gap-4 text-sm">
              <label className="flex items-center gap-2 text-slate-300">
                <input
                  type="checkbox"
                  checked={config.include_database}
                  onChange={(e) => setConfig({ ...config, include_database: e.target.checked })}
                />
                Incluir PostgreSQL nos backups
              </label>
              <label className="flex items-center gap-2 text-slate-300">
                <input
                  type="checkbox"
                  checked={config.include_faiss}
                  onChange={(e) => setConfig({ ...config, include_faiss: e.target.checked })}
                />
                Incluir FAISS
              </label>
              <label className="flex items-center gap-2 text-slate-300">
                <input
                  type="checkbox"
                  checked={config.include_knowledge_pdfs}
                  onChange={(e) => setConfig({ ...config, include_knowledge_pdfs: e.target.checked })}
                />
                Incluir PDFs no backup knowledge (grande)
              </label>
            </div>
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy !== null}
            onClick={saveConfig}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200 ring-1 ring-slate-700 disabled:opacity-50"
          >
            {busy === "config" ? "Salvando…" : "Salvar configuração"}
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={initFolders}
            className="rounded-lg bg-cyan-500/20 px-4 py-2 text-sm text-cyan-300 ring-1 ring-cyan-500/40 disabled:opacity-50"
          >
            {busy === "init" ? "Criando…" : "Criar estrutura de pastas"}
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {Object.entries(subfolders).map(([name, ok]) => (
            <span
              key={name}
              className={cn(
                "rounded-full px-2.5 py-1 text-xs ring-1",
                ok
                  ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
                  : "bg-slate-800 text-slate-500 ring-slate-700",
              )}
            >
              {name}{ok ? " ✓" : ""}
            </span>
          ))}
        </div>
      </section>

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h3 className="mb-3 text-sm font-semibold text-white">Executar backup</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          {BACKUP_TARGETS.map((t) => (
            <label
              key={t.id}
              className={cn(
                "flex cursor-pointer gap-3 rounded-xl p-3 ring-1 transition",
                selected.includes(t.id)
                  ? "bg-cyan-500/10 ring-cyan-500/30"
                  : "bg-slate-950/40 ring-slate-800 hover:ring-slate-700",
              )}
            >
              <input
                type="checkbox"
                className="mt-1"
                checked={selected.includes(t.id)}
                onChange={() => toggleTarget(t.id)}
              />
              <span>
                <span className="block text-sm font-medium text-slate-200">{t.label}</span>
                <span className="mt-0.5 block text-xs text-slate-500">{t.description}</span>
              </span>
            </label>
          ))}
        </div>
        <button
          type="button"
          disabled={busy !== null || !selected.length}
          onClick={runBackup}
          className="mt-4 rounded-lg bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-300 ring-1 ring-emerald-500/40 disabled:opacity-50"
        >
          {busy === "backup" ? "Executando backup…" : "Executar backup selecionado"}
        </button>
        <p className="mt-3 text-xs text-slate-500">
          Acompanhe jobs longos no{" "}
          <Link href="/console" className="text-cyan-400 hover:underline">
            Console
          </Link>
          . CLI: <code className="text-slate-400">make restore STAMP=YYYYMMDD-HHMMSS</code>
        </p>
      </section>

      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h3 className="mb-1 text-sm font-semibold text-white">Restaurar backup</h3>
        <p className="mb-4 text-sm text-slate-500">
          Restaura PostgreSQL, knowledge e FAISS a partir de um conjunto (stamp). Busca no staging
          local ou no Google Drive. Após restore de código (app), rode <code>make setup</code> e{" "}
          <code>ollama pull</code> nos modelos.
        </p>
        <div className="grid gap-3 sm:grid-cols-[1fr,auto]">
          <label className="block text-sm">
            <span className="mb-1 block text-slate-400">Stamp (YYYYMMDD-HHMMSS)</span>
            <input
              list="maintenance-stamps"
              value={restoreStamp}
              onChange={(e) => setRestoreStamp(e.target.value)}
              placeholder="20260621-165953"
              className="w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-200 ring-1 ring-slate-700"
            />
            <datalist id="maintenance-stamps">
              {availableStamps.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          </label>
          <div className="flex items-end">
            <button
              type="button"
              disabled={busy !== null || !restoreStamp.trim()}
              onClick={inspectRestore}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200 ring-1 ring-slate-700 disabled:opacity-50"
            >
              {busy === "inspect" ? "Inspecionando…" : "Inspecionar"}
            </button>
          </div>
        </div>
        {restoreInspect && (
          <p className="mt-2 text-xs text-slate-500">
            Disponível: {Object.keys(restoreInspect.artifacts).join(", ") || "nenhum"}
            {restoreInspect.missing.length > 0 && ` · Faltando: ${restoreInspect.missing.join(", ")}`}
          </p>
        )}
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {RESTORE_TARGETS.map((t) => (
            <label
              key={t.id}
              className={cn(
                "flex cursor-pointer gap-3 rounded-xl p-3 ring-1 transition",
                restoreTargets.includes(t.id)
                  ? "bg-violet-500/10 ring-violet-500/30"
                  : "bg-slate-950/40 ring-slate-800",
              )}
            >
              <input
                type="checkbox"
                className="mt-1"
                checked={restoreTargets.includes(t.id)}
                onChange={() => toggleRestoreTarget(t.id)}
              />
              <span className="text-sm font-medium text-slate-200">{t.label}</span>
            </label>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy !== null || !restoreStamp.trim()}
            onClick={() => runRestore(true)}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-200 ring-1 ring-slate-700 disabled:opacity-50"
          >
            {busy === "restore-dry" ? "Simulando…" : "Simular (dry-run)"}
          </button>
          <button
            type="button"
            disabled={busy !== null || !restoreStamp.trim() || !restoreTargets.length}
            onClick={() => runRestore(false)}
            className="rounded-lg bg-violet-500/20 px-4 py-2 text-sm font-medium text-violet-300 ring-1 ring-violet-500/40 disabled:opacity-50"
          >
            {busy === "restore" ? "Restaurando…" : "Restaurar agora"}
          </button>
        </div>
      </section>

      {(lastResult || (status?.history?.length ?? 0) > 0) && (
        <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
          <h3 className="mb-3 text-sm font-semibold text-white">Histórico recente</h3>
          <ul className="space-y-2 text-sm">
            {(lastResult ? [lastResult, ...(status?.history ?? [])] : status?.history ?? [])
              .slice(0, 8)
              .map((item) => (
                <li
                  key={item.id}
                  className="rounded-lg bg-slate-950/50 px-3 py-2 ring-1 ring-slate-800"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-slate-200">{item.id}</span>
                    <span
                      className={cn(
                        "text-xs",
                        item.status === "completed" ? "text-emerald-400" : "text-amber-400",
                      )}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {item.targets.join(", ")} · {item.artifacts?.length ?? 0} artefato(s)
                    {(item.errors?.length ?? 0) > 0 && ` · ${item.errors.length} erro(s)`}
                  </p>
                </li>
              ))}
          </ul>
        </section>
      )}

      {message && <p className="text-sm text-emerald-400">{message}</p>}
      {error && <p className="text-sm text-red-300">{error}</p>}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-950/50 px-3 py-2 ring-1 ring-slate-800">
      <p className="text-[10px] uppercase tracking-wider text-slate-600">{label}</p>
      <p className="mt-1 text-sm text-slate-200 break-all">{value}</p>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-400">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border-0 bg-slate-950 px-3 py-2 text-sm text-slate-200 ring-1 ring-slate-700 focus:ring-cyan-500/50"
      />
      {hint && <span className="mt-1 block text-xs text-slate-600">{hint}</span>}
    </label>
  );
}
