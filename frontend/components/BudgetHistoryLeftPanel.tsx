"use client";

import type { BudgetRow, BudgetSessionResponse, BudgetSummary } from "@/types/api";
import { sessionFinancialBreakdown } from "@/lib/budget-desoneracao";
import { cn } from "@/lib/utils";
import LoadingSpinner from "@/components/LoadingSpinner";

interface BudgetHistoryLeftPanelProps {
  items: BudgetSummary[];
  selectedId: string | null;
  preview: BudgetSessionResponse | null;
  previewLoading: boolean;
  className?: string;
}

function fmtMoney(n: number) {
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR");
}

function etapaTotal(row: BudgetRow): number {
  if (typeof row.total_effective === "number" && row.total_effective > 0) {
    return row.total_effective;
  }
  const comd = row.total_price ?? 0;
  const semd = row.total_price_semd ?? 0;
  if (semd > 0 && semd < comd) return semd;
  return comd;
}

function HistoryList({ items }: { items: BudgetSummary[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">Nenhum orçamento salvo ainda.</p>;
  }

  return (
    <ul className="max-h-[min(520px,60vh)] space-y-2 overflow-y-auto">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-center justify-between rounded-lg bg-slate-950/50 px-3 py-2.5 text-sm"
        >
          <div className="min-w-0 pr-3">
            <p className="truncate font-medium text-slate-200">{item.title}</p>
            {item.orcamento && (
              <p className="truncate font-mono text-[11px] text-cyan-400/80">{item.orcamento}</p>
            )}
            <p className="text-xs text-slate-500">
              {item.obra_type} · {fmtDate(item.updated_at)}
            </p>
          </div>
          <span className="shrink-0 text-sm font-semibold text-emerald-400">
            R$ {fmtMoney(item.grand_total)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function BudgetPreview({
  item,
  preview,
  loading,
}: {
  item: BudgetSummary;
  preview: BudgetSessionResponse | null;
  loading: boolean;
}) {
  const etapas =
    preview?.rows.filter((r) => r.row_type === "ETAPA" && r.level === 0) ?? [];

  const financial = preview ? sessionFinancialBreakdown(preview) : null;
  const money = (value: number | null | undefined) =>
    value != null ? `R$ ${fmtMoney(value)}` : loading ? "…" : "—";

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <div className="rounded-lg bg-slate-950/50 px-4 py-3">
        <h4 className="text-base font-semibold text-white">{item.title}</h4>
        {item.orcamento && (
          <p className="mt-0.5 font-mono text-xs text-cyan-400/90">{item.orcamento}</p>
        )}
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <div>
            <dt className="text-slate-500">Total sem BDI</dt>
            <dd className="font-medium text-slate-200">{money(financial?.adoptedCost)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Valor BDI</dt>
            <dd className="font-medium text-slate-200">{money(financial?.adoptedBdi)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Total com BDI</dt>
            <dd className="font-semibold text-emerald-400">
              {money(financial?.adoptedTotal ?? item.grand_total)}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Tipo de obra</dt>
            <dd className="text-slate-200">{item.obra_type}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Atualizado</dt>
            <dd className="text-slate-200">{fmtDate(item.updated_at)}</dd>
          </div>
          {preview?.project?.local && (
            <div>
              <dt className="text-slate-500">Local</dt>
              <dd className="truncate text-slate-200">{preview.project.local}</dd>
            </div>
          )}
        </dl>
      </div>

      <div className="min-h-0 flex-1">
        <h5 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">
          Etapas
        </h5>
        {loading ? (
          <div className="flex justify-center py-10">
            <LoadingSpinner label="Carregando etapas…" size="md" />
          </div>
        ) : etapas.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhuma etapa cadastrada neste orçamento.</p>
        ) : (
          <ul className="max-h-[min(380px,50vh)] space-y-1.5 overflow-y-auto">
            {etapas.map((etapa) => (
              <li
                key={etapa.row_id}
                className="flex items-start justify-between gap-3 rounded-lg bg-slate-950/40 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-violet-300/90">
                    Etapa {etapa.code}
                  </p>
                  <p className="truncate text-sm text-slate-200">{etapa.name}</p>
                </div>
                <span className="shrink-0 text-sm font-medium text-slate-300">
                  R$ {fmtMoney(etapaTotal(etapa))}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function BudgetHistoryLeftPanel({
  items,
  selectedId,
  preview,
  previewLoading,
  className,
}: BudgetHistoryLeftPanelProps) {
  const selectedItem = selectedId ? items.find((i) => i.id === selectedId) : null;

  return (
    <section
      className={cn(
        "flex min-h-[min(520px,60vh)] flex-col rounded-xl bg-slate-900/40 p-4 ring-1 ring-slate-800/80",
        className
      )}
    >
      <div className="mb-3">
        <h3 className="text-sm font-medium text-white">
          {selectedItem ? "Resumo do orçamento" : "Histórico de orçamentos"}
        </h3>
        <p className="text-xs text-slate-500">
          {selectedItem
            ? "Etapas do orçamento selecionado"
            : "Selecione um orçamento à direita para ver o resumo por etapas"}
        </p>
      </div>

      <div className="min-h-0 flex-1">
        {selectedItem ? (
          <BudgetPreview item={selectedItem} preview={preview} loading={previewLoading} />
        ) : (
          <HistoryList items={items} />
        )}
      </div>
    </section>
  );
}
