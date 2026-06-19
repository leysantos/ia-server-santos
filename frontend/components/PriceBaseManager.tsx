"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ActionDialog from "@/components/ActionDialog";
import LoadingSpinner from "@/components/LoadingSpinner";
import { api } from "@/services/api";
import type { PriceBaseActiveStatus, PriceBaseInfo } from "@/types/api";
import { cn, formatDate } from "@/lib/utils";

const ACCEPT = ".csv,.xlsx,.xls,.json,.xlsm,.xml,.pdf,.txt";

type DialogState = {
  open: boolean;
  title: string;
  message: string;
  variant: "success" | "error" | "confirm" | "info";
  onConfirm?: () => void;
};

export default function PriceBaseManager() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [bases, setBases] = useState<PriceBaseInfo[]>([]);
  const [activeStatus, setActiveStatus] = useState<PriceBaseActiveStatus | null>(null);
  const [baseName, setBaseName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogState>({
    open: false,
    title: "",
    message: "",
    variant: "info",
  });

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const result = await api.pricingListBases();
      setBases(result.bases);
      setActiveStatus(result.active ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar bases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleImport = async (file: File) => {
    const name = baseName.trim();
    if (!name) {
      setDialog({
        open: true,
        title: "Nome obrigatório",
        message: "Informe um nome para a base de preços antes de importar.",
        variant: "error",
      });
      return;
    }

    setBusy(true);
    try {
      const result = await api.pricingImportBase(name, file);
      setBaseName("");
      if (fileRef.current) fileRef.current.value = "";
      await refresh();
      setDialog({
        open: true,
        title: "Base importada",
        message: `"${result.base.name}" — ${result.loaded.toLocaleString("pt-BR")} itens carregados.`,
        variant: "success",
      });
    } catch (err) {
      setDialog({
        open: true,
        title: "Falha na importação",
        message: err instanceof Error ? err.message : "Erro desconhecido",
        variant: "error",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleImportExample = async () => {
    setBusy(true);
    try {
      const result = await api.pricingImportExampleBase();
      await refresh();
      setDialog({
        open: true,
        title: result.reactivated ? "Base reativada" : "Exemplo importado",
        message: `"${result.base.name}" — ${result.loaded.toLocaleString("pt-BR")} itens da planilha PPD de exemplo.`,
        variant: "success",
      });
    } catch (err) {
      setDialog({
        open: true,
        title: "Falha ao importar exemplo",
        message: err instanceof Error ? err.message : "Erro",
        variant: "error",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleActivate = async (baseId: string) => {
    setBusy(true);
    try {
      await api.pricingActivateBase(baseId);
      await refresh();
    } catch (err) {
      setDialog({
        open: true,
        title: "Falha ao ativar",
        message: err instanceof Error ? err.message : "Erro",
        variant: "error",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = (base: PriceBaseInfo) => {
    setDialog({
      open: true,
      title: "Excluir base de preços?",
      message: `Confirma exclusão de "${base.name}" (${base.item_count.toLocaleString("pt-BR")} itens)?`,
      variant: "confirm",
      onConfirm: async () => {
        setBusy(true);
        try {
          await api.pricingDeleteBase(base.id);
          await refresh();
          setDialog({
            open: true,
            title: "Base excluída",
            message: `"${base.name}" removida.`,
            variant: "success",
          });
        } catch (err) {
          setDialog({
            open: true,
            title: "Falha ao excluir",
            message: err instanceof Error ? err.message : "Erro",
            variant: "error",
          });
        } finally {
          setBusy(false);
        }
      },
    });
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <LoadingSpinner label="Carregando bases de preço…" />
      </div>
    );
  }

  const activeBase = bases.find((b) => b.active);
  const noBaseConfigured = !activeStatus?.loaded && bases.length === 0;

  return (
    <>
      <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
        <h2 className="mb-1 text-base font-semibold text-white">Bases de preço</h2>
        <p className="mb-6 text-sm text-slate-500">
          Importe e gerencie bases SINAPI, ORSE, TCPO ou planilhas PPD (.xlsm). O módulo de orçamento
          usa automaticamente a base <strong className="text-slate-400">ativa</strong> configurada aqui.
        </p>

        {error && (
          <div className="mb-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
            {error}
          </div>
        )}

        {noBaseConfigured && (
          <div className="mb-4 rounded-xl bg-amber-500/10 px-4 py-3 text-sm text-amber-200 ring-1 ring-amber-500/30">
            Nenhuma base configurada. Importe uma base abaixo ou use o exemplo PPD do sistema antes de
            gerar orçamentos.
          </div>
        )}

        {activeBase && (
          <div className="mb-6 rounded-xl bg-emerald-500/10 px-4 py-3 ring-1 ring-emerald-500/30">
            <p className="text-sm font-medium text-emerald-300">
              Base ativa: {activeBase.name}
            </p>
            <p className="mt-1 text-xs text-emerald-400/80">
              {activeBase.item_count.toLocaleString("pt-BR")} itens · {activeBase.format.toUpperCase()} ·{" "}
              {activeBase.filename}
            </p>
          </div>
        )}

        <div className="mb-6 space-y-3 rounded-xl bg-slate-950/40 p-4 ring-1 ring-slate-800">
          <div>
            <label className="text-xs text-slate-500">Nome da base</label>
            <input
              type="text"
              value={baseName}
              onChange={(e) => setBaseName(e.target.value)}
              placeholder="Ex: SINAPI Mar/2026, ORSE AM, TCPO SP..."
              disabled={busy}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none disabled:opacity-50"
            />
          </div>

          <label
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-4 py-8 text-sm transition",
              baseName.trim()
                ? "border-slate-600 text-slate-400 hover:border-cyan-500/50 hover:text-cyan-300"
                : "pointer-events-none border-slate-700/50 text-slate-600 opacity-60"
            )}
          >
            {busy ? "Importando…" : "Selecionar arquivo (CSV, Excel, XML, PDF, JSON, PPD .xlsm)"}
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPT}
              className="hidden"
              disabled={busy || !baseName.trim()}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleImport(file);
              }}
            />
          </label>

          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              disabled={busy}
              onClick={handleImportExample}
              className="rounded-lg bg-violet-600/20 px-4 py-2 text-sm font-medium text-violet-300 ring-1 ring-violet-500/40 hover:bg-violet-600/30 disabled:opacity-50"
            >
              Importar exemplo PPD do sistema
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => refresh()}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-300 ring-1 ring-slate-700 hover:bg-slate-700 disabled:opacity-50"
            >
              Atualizar lista
            </button>
          </div>
        </div>

        {bases.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            Nenhuma base importada ainda.
          </p>
        ) : (
          <div className="overflow-auto rounded-xl ring-1 ring-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/95 text-xs uppercase text-slate-500">
                <tr className="border-b border-slate-800">
                  <th className="px-4 py-3 font-medium">Nome</th>
                  <th className="px-4 py-3 font-medium">Arquivo</th>
                  <th className="px-4 py-3 font-medium">Itens</th>
                  <th className="px-4 py-3 font-medium">Importado</th>
                  <th className="px-4 py-3 font-medium">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {bases.map((base) => (
                  <tr key={base.id} className="hover:bg-slate-800/30">
                    <td className="px-4 py-3">
                      <span className="text-slate-200">{base.name}</span>
                      {base.active && (
                        <span className="ml-2 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300 ring-1 ring-emerald-500/30">
                          ativa
                        </span>
                      )}
                    </td>
                    <td className="max-w-[10rem] truncate px-4 py-3 text-slate-400" title={base.filename}>
                      {base.filename}
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {base.item_count.toLocaleString("pt-BR")}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                      {formatDate(base.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        {!base.active && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => handleActivate(base.id)}
                            className="rounded bg-cyan-600/20 px-2 py-1 text-xs text-cyan-300 ring-1 ring-cyan-500/40 hover:bg-cyan-600/30 disabled:opacity-50"
                          >
                            Ativar
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleDelete(base)}
                          className="rounded bg-red-600/10 px-2 py-1 text-xs text-red-300 ring-1 ring-red-500/30 hover:bg-red-600/20 disabled:opacity-50"
                        >
                          Excluir
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        variant={dialog.variant}
        confirmLabel={dialog.variant === "confirm" ? "Excluir" : "OK"}
        onConfirm={dialog.onConfirm}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
      />
    </>
  );
}
