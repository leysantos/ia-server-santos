import type { BudgetRow, BudgetSessionResponse } from "@/types/api";

export type DesoneracaoMode = "comd" | "semd";

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/** Totais ComD e SemD por linha (com BDI). */
export function rowDualTotals(row: BudgetRow): { comd: number; semd: number } {
  return {
    comd: row.total_price ?? 0,
    semd: row.total_price_semd ?? 0,
  };
}

/** Custo direto sem BDI por linha. */
export function rowCostTotals(row: BudgetRow): { comd: number; semd: number } {
  if (row.row_type !== "S" || row.is_memory_row) {
    return { comd: 0, semd: 0 };
  }
  const qty = row.quantity ?? 0;
  return {
    comd: round2(qty * (row.unit_cost ?? 0)),
    semd: round2(qty * (row.unit_cost_semd ?? row.unit_cost ?? 0)),
  };
}

export function rowWinningMode(comd: number, semd: number): DesoneracaoMode | null {
  if (comd <= 0 && semd <= 0) return null;
  if (semd <= 0) return "comd";
  if (comd <= 0) return "semd";
  return semd < comd ? "semd" : "comd";
}

export function sessionPureTotals(session: BudgetSessionResponse) {
  return {
    comd: session.grand_total_comd ?? 0,
    semd: session.grand_total_semd ?? 0,
  };
}

export function sessionCostTotals(session: BudgetSessionResponse) {
  let comd = 0;
  let semd = 0;
  for (const row of session.rows) {
    const c = rowCostTotals(row);
    comd += c.comd;
    semd += c.semd;
  }
  return { comd: round2(comd), semd: round2(semd) };
}

export interface SessionFinancialBreakdown {
  costComd: number;
  costSemd: number;
  bdiComd: number;
  bdiSemd: number;
  totalComd: number;
  totalSemd: number;
  adoptedTotal: number;
  adoptedMode: DesoneracaoMode;
  adoptedCost: number;
  adoptedBdi: number;
}

export function sessionFinancialBreakdown(session: BudgetSessionResponse): SessionFinancialBreakdown {
  const { comd: totalComd, semd: totalSemd } = sessionPureTotals(session);
  const { comd: costComd, semd: costSemd } = sessionCostTotals(session);
  const adoptedMode = sessionWinningMode(session);
  const adoptedTotal = sessionMinimumTotal(session);
  const adoptedCost = adoptedMode === "semd" ? costSemd : costComd;
  const adoptedBdi = adoptedMode === "semd" ? round2(totalSemd - costSemd) : round2(totalComd - costComd);

  return {
    costComd,
    costSemd,
    bdiComd: round2(totalComd - costComd),
    bdiSemd: round2(totalSemd - costSemd),
    totalComd,
    totalSemd,
    adoptedTotal,
    adoptedMode,
    adoptedCost,
    adoptedBdi,
  };
}

/** Menor valor entre os totais integrais ComD e SemD. */
export function sessionMinimumTotal(session: BudgetSessionResponse): number {
  const { comd, semd } = sessionPureTotals(session);
  if (semd > 0 && semd < comd) return semd;
  return comd;
}

export function sessionWinningMode(session: BudgetSessionResponse): DesoneracaoMode {
  const { comd, semd } = sessionPureTotals(session);
  return rowWinningMode(comd, semd) ?? "comd";
}

/** Com desoneração = azul; sem desoneração = verde. */
export function modeColorClass(mode: DesoneracaoMode, bold = false): string {
  const base = bold ? "font-semibold tabular-nums" : "tabular-nums";
  return mode === "comd" ? `${base} text-blue-400` : `${base} text-emerald-400`;
}

/** @deprecated use modeColorClass */
export function totalCellClass(mode: DesoneracaoMode, _winning?: DesoneracaoMode | null, bold = false): string {
  return modeColorClass(mode, bold);
}

export function bdiComdLabel(session: BudgetSessionResponse): string {
  const rate = session.project?.bdi?.rate_com_desoneracao;
  const pct = rate != null ? (rate * 100).toFixed(2).replace(".", ",") : "—";
  const code = session.project?.obra_type || session.project?.bdi?.obra_type || "RF";
  return `Com desoneração (BDI ${code} ${pct}%)`;
}

export function bdiSemdLabel(session: BudgetSessionResponse): string {
  const rate = session.project?.bdi?.rate_sem_desoneracao;
  const pct = rate != null ? (rate * 100).toFixed(2).replace(".", ",") : "—";
  return `Sem desoneração (BDI ${pct}%)`;
}

export function fmtMoney(n: number | undefined | null): string {
  if (n == null || n === 0) return "—";
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
