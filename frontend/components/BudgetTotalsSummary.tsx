"use client";

import type { BudgetSessionResponse } from "@/types/api";
import {
  fmtMoney,
  modeColorClass,
  sessionFinancialBreakdown,
  type SessionFinancialBreakdown,
} from "@/lib/budget-desoneracao";
import { cn } from "@/lib/utils";

interface BudgetTotalsSummaryProps {
  session: BudgetSessionResponse;
  compact?: boolean;
  detailed?: boolean;
}

function formatMoneyValue(n: number): string {
  return `R$ ${fmtMoney(n) === "—" ? "0,00" : fmtMoney(n)}`;
}

function useTotalsPresentation(session: BudgetSessionResponse) {
  const b = sessionFinancialBreakdown(session);
  const showSemd = b.totalSemd > 0 || b.costSemd > 0;
  const money = formatMoneyValue;
  return { b, showSemd, money };
}

function TotalsDetailRows({
  b,
  showSemd,
  money,
  className,
}: {
  b: SessionFinancialBreakdown;
  showSemd: boolean;
  money: (n: number) => string;
  className?: string;
}) {
  const row = (label: string, comd: number, semd: number, bold = false) => (
    <div
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-6 gap-y-1 px-4 py-2 text-sm",
        bold && "bg-slate-800/70 font-semibold"
      )}
    >
      <span className={cn("text-right", bold ? "text-slate-200" : "text-slate-400")}>{label}</span>
      <span className={cn("text-right", modeColorClass("comd", bold))}>{money(comd)}</span>
      <span className={cn("text-right", showSemd ? modeColorClass("semd", bold) : "text-slate-600")}>
        {showSemd ? money(semd) : "—"}
      </span>
    </div>
  );

  return (
    <div className={className}>
      {row("Total sem BDI (custo direto)", b.costComd, b.costSemd)}
      {row("Valor BDI", b.bdiComd, b.bdiSemd)}
      {row("Total com BDI", b.totalComd, b.totalSemd, true)}
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-6 border-t border-slate-700/50 bg-slate-900/80 px-4 py-3">
        <span className="text-right font-semibold text-slate-200">Total adotado (menor valor)</span>
        <span className="text-right text-lg font-semibold tabular-nums text-white">
          {money(b.adoptedTotal)}
        </span>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-6 bg-slate-900/50 px-4 pb-3 pt-1 text-xs">
        <span className="text-right text-slate-500">
          Composição do total adotado ({b.adoptedMode === "semd" ? "SemD" : "ComD"})
        </span>
        <span className="text-right text-slate-500">
          Custo {money(b.adoptedCost)} + BDI {money(b.adoptedBdi)}
        </span>
      </div>
    </div>
  );
}

export function BudgetTotalsDetailPanel({ session }: { session: BudgetSessionResponse }) {
  const { b, showSemd, money } = useTotalsPresentation(session);

  return (
    <div className="overflow-hidden rounded-xl bg-slate-900/40 ring-1 ring-slate-800">
      <TotalsDetailRows b={b} showSemd={showSemd} money={money} />
    </div>
  );
}

export default function BudgetTotalsSummary({ session, compact, detailed }: BudgetTotalsSummaryProps) {
  const { b, showSemd } = useTotalsPresentation(session);

  if (detailed) {
    return <BudgetTotalsDetailPanel session={session} />;
  }

  if (compact) {
    return (
      <div className="flex flex-col items-end gap-2 text-sm">
        <div className="grid w-full max-w-2xl grid-cols-[1fr_auto_auto] items-center gap-x-4 gap-y-1.5 text-xs">
          <span />
          <span className={`text-center ${modeColorClass("comd", true)}`}>ComD</span>
          {showSemd ? (
            <span className={`text-center ${modeColorClass("semd", true)}`}>SemD</span>
          ) : (
            <span />
          )}
          <span className="text-slate-500 text-right">Total sem BDI</span>
          <span className={modeColorClass("comd", true)}>R$ {fmtMoney(b.costComd)}</span>
          {showSemd ? (
            <span className={modeColorClass("semd", true)}>R$ {fmtMoney(b.costSemd)}</span>
          ) : (
            <span />
          )}

          <span className="text-slate-500 text-right">Valor BDI</span>
          <span className={modeColorClass("comd", true)}>R$ {fmtMoney(b.bdiComd)}</span>
          {showSemd ? (
            <span className={modeColorClass("semd", true)}>R$ {fmtMoney(b.bdiSemd)}</span>
          ) : (
            <span />
          )}

          <span className="text-slate-400 text-right">Total com BDI</span>
          <span className={modeColorClass("comd", true)}>R$ {fmtMoney(b.totalComd)}</span>
          {showSemd ? (
            <span className={modeColorClass("semd", true)}>R$ {fmtMoney(b.totalSemd)}</span>
          ) : (
            <span />
          )}
        </div>

        <div className="mt-1 border-t border-slate-700/50 pt-2 text-right">
          <span className="text-slate-300">
            Total adotado (menor valor):{" "}
            <strong className="text-base text-white">R$ {fmtMoney(b.adoptedTotal)}</strong>
          </span>
          <span className="ml-2 text-xs text-slate-500">
            (custo R$ {fmtMoney(b.adoptedCost)} + BDI R$ {fmtMoney(b.adoptedBdi)})
          </span>
        </div>
      </div>
    );
  }

  return null;
}

/** Linhas de rodapé para a planilha (colSpan label + col ComD + col SemD). */
export function BudgetSpreadsheetFooterRows({
  session,
  colSpan,
}: {
  session: BudgetSessionResponse;
  colSpan: number;
}) {
  const { b, showSemd, money } = useTotalsPresentation(session);

  const row = (label: string, comd: number, semd: number, bold = false) => (
    <tr className={bold ? "bg-slate-800/70 font-semibold text-sm" : "bg-slate-800/40 text-sm"}>
      <td colSpan={colSpan} className="px-3 py-2 text-right text-slate-400">
        {label}
      </td>
      <td className={`px-3 py-2 text-right ${modeColorClass("comd", bold)}`}>{money(comd)}</td>
      <td className={`px-3 py-2 text-right ${modeColorClass("semd", bold)}`}>
        {showSemd ? money(semd) : "—"}
      </td>
      <td />
    </tr>
  );

  return (
    <>
      {row("Total sem BDI (custo direto)", b.costComd, b.costSemd)}
      {row("Valor BDI", b.bdiComd, b.bdiSemd)}
      {row("Total com BDI", b.totalComd, b.totalSemd, true)}
      <tr className="bg-slate-900/80 font-semibold">
        <td colSpan={colSpan} className="px-3 py-3 text-right text-slate-200">
          Total adotado (menor valor)
        </td>
        <td colSpan={2} className="px-3 py-3 text-right text-lg tabular-nums text-white">
          {money(b.adoptedTotal)}
        </td>
        <td />
      </tr>
      <tr className="bg-slate-900/50 text-xs">
        <td colSpan={colSpan} className="px-3 pb-3 text-right text-slate-500">
          Composição do total adotado ({b.adoptedMode === "semd" ? "SemD" : "ComD"})
        </td>
        <td colSpan={2} className="px-3 pb-3 text-right text-slate-500">
          Custo {money(b.adoptedCost)} + BDI {money(b.adoptedBdi)}
        </td>
        <td />
      </tr>
    </>
  );
}
