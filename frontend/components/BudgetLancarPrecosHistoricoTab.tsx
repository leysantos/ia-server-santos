"use client";

import { useCallback, useEffect, useState } from "react";
import LoadingSpinner from "@/components/LoadingSpinner";
import { api } from "@/services/api";
import type { PriceMatchingJob } from "@/types/api";
import { budgetBtn } from "@/lib/budget-ui";
import { cn } from "@/lib/utils";

const STATUS_LABELS: Record<string, string> = {
  draft: "Rascunho",
  imported: "Importado",
  processing: "Processando",
  done: "Processado",
  budget_generated: "Orçamento gerado",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function formatWhen(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

interface BudgetLancarPrecosHistoricoTabProps {
  activeJobId?: string | null;
  onOpen: (jobId: string) => void;
  onOpenBudgetModule?: (job: PriceMatchingJob) => void;
  onReprocess: (jobId: string) => void;
  onDelete: (jobId: string) => void;
  onError?: (err: unknown, title?: string) => void;
  refreshToken?: number;
}

export default function BudgetLancarPrecosHistoricoTab({
  activeJobId,
  onOpen,
  onOpenBudgetModule,
  onReprocess,
  onDelete,
  onError,
  refreshToken = 0,
}: BudgetLancarPrecosHistoricoTabProps) {
  const [jobs, setJobs] = useState<PriceMatchingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.priceMatchingListJobs(80);
      setJobs(res.jobs ?? []);
    } catch (e) {
      onError?.(e, "Carregar histórico");
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs, refreshToken]);

  const handleReprocess = async (jobId: string) => {
    setBusyId(jobId);
    try {
      await onReprocess(jobId);
      await loadJobs();
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <LoadingSpinner label="Carregando histórico…" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/5 bg-surface-card/40 p-4">
        <h2 className="text-sm font-semibold text-slate-100">Histórico — Lançar Preços</h2>
        <p className="mt-1 text-xs text-slate-500">
          Orçamentos importados e processados neste módulo. Abra para revisar, reprocesse preços ou exclua.
        </p>
      </div>

      {jobs.length === 0 ? (
        <p className="rounded-xl border border-dashed border-white/10 py-12 text-center text-sm text-slate-500">
          Nenhum orçamento processado ainda. Importe uma planilha na aba Lançar Preços.
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {jobs.map((job) => {
            const isActive = activeJobId === job.id;
            const isBusy = busyId === job.id;
            const title = job.obra || job.cliente || job.source_filename || job.title || "Orçamento";
            return (
              <li
                key={job.id}
                className={cn(
                  "flex flex-col rounded-xl border bg-slate-900/50 p-4 ring-1 transition-colors",
                  isActive
                    ? "border-cyan-500/40 ring-cyan-500/30"
                    : "border-white/5 ring-slate-800/80 hover:border-white/10"
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-100" title={title}>
                    {title}
                  </p>
                  {job.source_filename && (
                    <p className="mt-0.5 truncate text-[11px] text-slate-500">{job.source_filename}</p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                    <span className="rounded-md bg-slate-800/80 px-2 py-0.5 text-slate-300">
                      {statusLabel(job.status)}
                    </span>
                    <span className="text-slate-500">
                      {job.rows_matched ?? 0}/{job.rows_total ?? 0} matched
                    </span>
                  </div>
                  <p className="mt-2 text-[10px] text-slate-600">
                    Atualizado {formatWhen(job.updated_at || job.processed_at || job.created_at)}
                  </p>
                </div>
                <div className="mt-4 flex flex-col gap-2">
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onOpen(job.id)}
                      className={cn(
                        budgetBtn,
                        "flex-1 bg-cyan-600/20 text-cyan-100 ring-cyan-500/30 hover:bg-cyan-600/30"
                      )}
                    >
                      Abrir
                    </button>
                    <button
                      type="button"
                      disabled={isBusy || job.status === "processing" || !(job.rows_total ?? 0)}
                      onClick={() => void handleReprocess(job.id)}
                      className={cn(
                        budgetBtn,
                        "flex-1 bg-emerald-700/25 text-emerald-100 ring-emerald-500/30 hover:bg-emerald-700/35"
                      )}
                    >
                      {isBusy ? "…" : "Processar"}
                    </button>
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onDelete(job.id)}
                      className={cn(
                        budgetBtn,
                        "bg-red-900/25 text-red-200 ring-red-500/30 hover:bg-red-900/40"
                      )}
                    >
                      Excluir
                    </button>
                  </div>
                  <button
                    type="button"
                    disabled={isBusy || !job.budget_document_id}
                    title={
                      job.budget_document_id
                        ? "Abrir no módulo Orçamento completo (etapas, sintético, exportação)"
                        : "Disponível após aplicar preços e salvar o orçamento"
                    }
                    onClick={() => onOpenBudgetModule?.(job)}
                    className={cn(
                      budgetBtn,
                      "w-full bg-violet-700/20 text-violet-100 ring-violet-500/30 hover:bg-violet-700/30 disabled:opacity-40"
                    )}
                  >
                    Abrir módulo de orçamento
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
