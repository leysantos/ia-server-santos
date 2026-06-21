"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import type { DevServiceItem, DevServicesResponse, ShellRunResponse } from "@/types/api";
import { cn } from "@/lib/utils";

const QUICK_COMMANDS = [
  { label: "make api", command: "make api", note: "Rode em terminal separado — não via UI" },
  { label: "make docker-up", command: "make docker-up" },
  { label: "make db-init", command: "make db-init" },
  { label: "docker ps", command: "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'" },
  { label: "git status", command: "git status -sb" },
];

function statusBadge(status: DevServiceItem["status"]) {
  if (status === "running") return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
  if (status === "stopped") return "bg-zinc-500/15 text-zinc-600 dark:text-zinc-400";
  return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
}

export default function SettingsServersPage() {
  const [data, setData] = useState<DevServicesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [command, setCommand] = useState("");
  const [cwd, setCwd] = useState("");
  const [shellOutput, setShellOutput] = useState<string>("");
  const [lastRun, setLastRun] = useState<ShellRunResponse | null>(null);
  const outputRef = useRef<HTMLPreElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.devopsServices();
      setData(resp);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar serviços");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 8000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [shellOutput]);

  const startCore = async () => {
    setBusy("stack");
    setError(null);
    setMessage(null);
    try {
      const result = await api.devopsStartCoreStack();
      setData((prev) => (prev ? { ...prev, services: result.services } : prev));
      const summary = result.results.map((r) => `${r.id}: ${r.action}`).join(", ");
      setMessage(`Stack backend: ${summary}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao subir stack");
    } finally {
      setBusy(null);
    }
  };

  const toggleService = async (service: DevServiceItem, action: "start" | "stop") => {
    setBusy(`${action}-${service.id}`);
    setError(null);
    setMessage(null);
    try {
      const result =
        action === "start"
          ? await api.devopsStartService(service.id)
          : await api.devopsStopService(service.id);
      setData((prev) => (prev ? { ...prev, services: result.services } : prev));
      setMessage(result.message || `${service.label} ${action === "start" ? "iniciado" : "parado"}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Erro ao ${action} ${service.label}`);
    } finally {
      setBusy(null);
    }
  };

  const viewLogs = async (serviceId: string) => {
    setBusy(`logs-${serviceId}`);
    try {
      const { log } = await api.devopsServiceLogs(serviceId);
      setShellOutput(log || "(sem logs)");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao ler logs");
    } finally {
      setBusy(null);
    }
  };

  const runCommand = async (cmd?: string) => {
    const toRun = (cmd ?? command).trim();
    if (!toRun) return;
    if (toRun.includes("make api") || toRun.startsWith("uvicorn")) {
      setError("A API não pode ser iniciada pelo console embutido — use um terminal com make api");
      return;
    }
    setBusy("shell");
    setError(null);
    setMessage(null);
    try {
      const result = await api.devopsShellRun(toRun, cwd || undefined);
      setLastRun(result);
      const header = `$ ${result.command}\n# cwd: ${result.cwd} | exit: ${result.exit_code}\n\n`;
      setShellOutput((prev) => `${prev}${prev ? "\n\n" : ""}${header}${result.output}`);
      if (!cmd) setCommand("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao executar comando");
    } finally {
      setBusy(null);
    }
  };

  const coreServices = data?.services.filter((s) => s.group === "core") ?? [];
  const optionalServices = data?.services.filter((s) => s.group === "optional") ?? [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Serviços de desenvolvimento</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Controle PostgreSQL e serviços opcionais. A API ({`make api`}) e o frontend ({`npm run dev`}) devem
          ser iniciados manualmente em terminais separados.
        </p>
      </div>

      {(error || message) && (
        <div
          className={cn(
            "rounded-lg border px-4 py-3 text-sm",
            error
              ? "border-red-500/30 bg-red-500/10 text-red-800 dark:text-red-200"
              : "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
          )}
        >
          {error || message}
        </div>
      )}

      <section className="rounded-xl border bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-medium">Stack backend</h2>
            <p className="text-sm text-muted-foreground">
              Sobe PostgreSQL (Docker) e executa db-init se necessário.
            </p>
          </div>
          <button
            type="button"
            disabled={!!busy || loading}
            onClick={startCore}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {busy === "stack" ? "Subindo…" : "Subir stack backend"}
          </button>
        </div>
        {data?.hints && (
          <ul className="mt-4 space-y-1 text-xs text-muted-foreground">
            {Object.entries(data.hints).map(([key, hint]) => (
              <li key={key}>
                <span className="font-mono">{key}</span>: {hint}
              </li>
            ))}
          </ul>
        )}
      </section>

      <ServiceGroup
        title="Núcleo"
        services={coreServices}
        loading={loading}
        busy={busy}
        onStart={(s) => toggleService(s, "start")}
        onStop={(s) => toggleService(s, "stop")}
        onLogs={viewLogs}
      />

      {optionalServices.length > 0 && (
        <ServiceGroup
          title="Opcional (workflow)"
          services={optionalServices}
          loading={loading}
          busy={busy}
          onStart={(s) => toggleService(s, "start")}
          onStop={(s) => toggleService(s, "stop")}
          onLogs={viewLogs}
        />
      )}

      <section className="rounded-xl border bg-card p-5 shadow-sm">
        <h2 className="font-medium">Console bash</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Executa comandos no repositório ({data?.repo_root ?? "…"}). Comandos destrutivos são bloqueados.
          Ambiente local apenas — não exponha na internet.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {QUICK_COMMANDS.map((q) => (
            <button
              key={q.label}
              type="button"
              title={q.note}
              disabled={!!busy}
              onClick={() => runCommand(q.command)}
              className="rounded-md border px-2.5 py-1 text-xs hover:bg-muted disabled:opacity-50"
            >
              {q.label}
            </button>
          ))}
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-[1fr,200px]">
          <input
            type="text"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runCommand()}
            placeholder="Ex.: make docker-up"
            className="rounded-md border bg-background px-3 py-2 font-mono text-sm"
          />
          <input
            type="text"
            value={cwd}
            onChange={(e) => setCwd(e.target.value)}
            placeholder="cwd (opcional, relativo)"
            className="rounded-md border bg-background px-3 py-2 font-mono text-sm"
          />
        </div>

        <div className="mt-3 flex gap-2">
          <button
            type="button"
            disabled={!!busy || !command.trim()}
            onClick={() => runCommand()}
            className="rounded-md bg-zinc-800 px-4 py-2 text-sm text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-200 dark:text-zinc-900"
          >
            {busy === "shell" ? "Executando…" : "Executar"}
          </button>
          <button
            type="button"
            onClick={() => setShellOutput("")}
            className="rounded-md border px-4 py-2 text-sm hover:bg-muted"
          >
            Limpar saída
          </button>
        </div>

        <pre
          ref={outputRef}
          className="mt-4 max-h-[420px] overflow-auto rounded-lg bg-zinc-950 p-4 font-mono text-xs leading-relaxed text-zinc-100"
        >
          {shellOutput || "# Saída dos comandos aparecerá aqui"}
        </pre>

        {lastRun && (
          <p className="mt-2 text-xs text-muted-foreground">
            Último: exit {lastRun.exit_code}
            {lastRun.truncated ? " (saída truncada)" : ""}
          </p>
        )}
      </section>
    </div>
  );
}

function ServiceGroup({
  title,
  services,
  loading,
  busy,
  onStart,
  onStop,
  onLogs,
}: {
  title: string;
  services: DevServiceItem[];
  loading: boolean;
  busy: string | null;
  onStart: (s: DevServiceItem) => void;
  onStop: (s: DevServiceItem) => void;
  onLogs: (id: string) => void;
}) {
  return (
    <section className="rounded-xl border bg-card p-5 shadow-sm">
      <h2 className="font-medium">{title}</h2>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {loading && services.length === 0 ? (
          <p className="text-sm text-muted-foreground">Carregando…</p>
        ) : (
          services.map((service) => (
            <div key={service.id} className="rounded-lg border p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium">{service.label}</h3>
                    <span className={cn("rounded-full px-2 py-0.5 text-xs", statusBadge(service.status))}>
                      {service.status}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{service.description}</p>
                  {service.detail && (
                    <p className="mt-1 font-mono text-xs text-muted-foreground">{service.detail}</p>
                  )}
                  {service.port && (
                    <p className="mt-1 text-xs text-muted-foreground">Porta {service.port}</p>
                  )}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {service.can_start && (
                  <button
                    type="button"
                    disabled={!!busy}
                    onClick={() => onStart(service)}
                    className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    Iniciar
                  </button>
                )}
                {service.can_stop && (
                  <button
                    type="button"
                    disabled={!!busy}
                    onClick={() => onStop(service)}
                    className="rounded-md bg-red-600/90 px-3 py-1.5 text-xs text-white hover:bg-red-500 disabled:opacity-50"
                  >
                    Parar
                  </button>
                )}
                {service.log_file && (
                  <button
                    type="button"
                    disabled={!!busy}
                    onClick={() => onLogs(service.id)}
                    className="rounded-md border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
                  >
                    Logs
                  </button>
                )}
                {!service.managed && service.status === "stopped" && (
                  <span className="text-xs text-muted-foreground">Manual</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
