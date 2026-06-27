/**
 * Valida Curva ABC, Curva S e Histograma contra payload de orçamento salvo.
 * Uso: npx tsx scripts/validate-budget-analytics.mts /tmp/projeto_teste_budget.json [/tmp/compositions.json]
 */
import { readFileSync } from "node:fs";
import type { BudgetRow, OpenCompositionDetail, ProjectSchedule } from "../types/api";
import {
  buildAbcCurve,
  buildScurvePoints,
  buildStackedHistogram,
} from "../lib/budget-analytics";

interface BudgetPayload {
  rows: BudgetRow[];
  schedule?: ProjectSchedule;
  project?: { projeto?: string; grand_total?: number };
  grand_total?: number;
}

const budgetPath = process.argv[2] ?? "/tmp/projeto_teste_budget.json";
const compPath = process.argv[3];

const payload = JSON.parse(readFileSync(budgetPath, "utf8")) as BudgetPayload;
const rows = payload.rows ?? [];
const schedule = payload.schedule ?? null;

const compositions = new Map<string, OpenCompositionDetail>();
if (compPath) {
  const raw = JSON.parse(readFileSync(compPath, "utf8")) as Record<string, OpenCompositionDetail>;
  for (const [k, v] of Object.entries(raw)) compositions.set(k, v);
}

const services = rows.filter((r) => r.row_type === "S" && !r.is_memory_row);
const serviceTotal = services.reduce(
  (s, r) => s + Math.max(0, r.total_effective ?? r.total_price ?? 0),
  0
);

console.log("=== PROJETO TESTE — Validação analítica ===\n");
console.log(`Serviços (S): ${services.length}`);
console.log(`Soma total_effective serviços: R$ ${serviceTotal.toFixed(2)}`);
console.log(`CPUs carregadas: ${compositions.size}`);
console.log(`Cronograma: ${schedule?.project_start ?? "—"} → ${schedule?.project_end ?? "—"}`);
console.log(`Tarefas cronograma: ${schedule?.tasks?.length ?? 0}\n`);

// --- Curva ABC ---
const abc = buildAbcCurve(rows);
const abcSum = abc.reduce((s, i) => s + i.value, 0);
const abcPctSum = abc.reduce((s, i) => s + i.pct, 0);
const abcLastCum = abc[abc.length - 1]?.cumulativePct ?? 0;

console.log("--- CURVA ABC ---");
console.log(`Itens ABC: ${abc.length}`);
console.log(`Soma valores ABC: R$ ${abcSum.toFixed(2)} (delta serviços: ${(abcSum - serviceTotal).toFixed(2)})`);
console.log(`Soma %: ${abcPctSum.toFixed(4)}% (esperado ~100%)`);
console.log(`% acumulado final: ${abcLastCum.toFixed(4)}%`);
console.log("Top 3:");
for (const item of abc.slice(0, 3)) {
  console.log(
    `  ${item.code} | R$ ${item.value.toFixed(2)} | ${item.pct.toFixed(2)}% | cum ${item.cumulativePct.toFixed(2)}% | ${item.abcClass}`
  );
}
const abcOk = Math.abs(abcSum - serviceTotal) < 0.02 && Math.abs(abcPctSum - 100) < 0.01;
console.log(`ABC OK: ${abcOk ? "SIM" : "NÃO"}\n`);

// --- Curva S ---
const scurve = buildScurvePoints(schedule, rows);
console.log("--- CURVA S ---");
console.log(`Meses: ${scurve.points.length}`);
console.log(`totalFinancial (engine): R$ ${scurve.totalFinancial.toFixed(2)}`);
console.log(`delta vs serviços: R$ ${(scurve.totalFinancial - serviceTotal).toFixed(2)}`);

if (scurve.points.length > 0) {
  const last = scurve.points[scurve.points.length - 1]!;
  const sumMonthlyFin = scurve.points.reduce((s, p) => s + p.financialMonthly, 0);
  console.log(`Soma financialMonthly: R$ ${sumMonthlyFin.toFixed(2)}`);
  console.log(`financialCumulative último mês: R$ ${last.financialCumulative.toFixed(2)} (${last.financialCumulativePct.toFixed(2)}%)`);
  console.log(`physicalCumulative último mês: ${last.physicalCumulativePct.toFixed(2)}%`);

  const finMatchTotal = Math.abs(last.financialCumulative - scurve.totalFinancial) < 1;
  const monthlyMatchTotal = Math.abs(sumMonthlyFin - scurve.totalFinancial) < 1;
  console.log(`Cumulativo = totalFinancial: ${finMatchTotal ? "SIM" : "NÃO"}`);
  console.log(`Σ mensal = totalFinancial: ${monthlyMatchTotal ? "SIM" : "NÃO"}`);
  console.log(`Cumulativo = soma serviços: ${Math.abs(last.financialCumulative - serviceTotal) < 1 ? "SIM" : "NÃO"}`);
}
console.log("");

// --- Histograma ---
const hist = buildStackedHistogram(schedule, rows, compositions, "comd", payload.project);
console.log("--- HISTOGRAMA (empilhado R$) ---");
console.log(`Meses: ${hist.months.length}`);
console.log(`Serviços com CPU: ${hist.servicesWithCpu}`);
console.log(
  `Totais EQ/INS/MO: R$ ${hist.totals.equipamento.toFixed(2)} / R$ ${hist.totals.insumo.toFixed(2)} / R$ ${hist.totals.mao_obra.toFixed(2)}`
);
console.log(`Total histograma: R$ ${hist.totals.total.toFixed(2)}`);
console.log(`Total ref. BDI: R$ ${hist.totals.totalWithBdi.toFixed(2)}`);
console.log(
  `Delta ref. BDI vs total efetivo serviços: R$ ${(hist.totals.totalWithBdi - serviceTotal).toFixed(2)}`
);

let analiticExpected = 0;
for (const s of services) {
  const d = compositions.get(s.row_id);
  if (!d) continue;
  const qty = s.quantity ?? 1;
  for (const item of d.items) {
    const cat = item.item_type?.toLowerCase();
    if (cat === "equipamento" || cat === "insumo" || cat === "mao_obra" || cat === "material") {
      analiticExpected += (item.partial_cost ?? 0) * qty;
    }
  }
}
console.log(`Soma analítica CPUs carregadas (ComD, qty serviço): R$ ${analiticExpected.toFixed(2)}`);
console.log(`Delta histograma vs analítico: R$ ${(hist.totals.total - analiticExpected).toFixed(2)}`);

const histMonthlySum = hist.months.reduce((s, m) => s + m.total, 0);
const histPartsSum =
  hist.totals.equipamento + hist.totals.insumo + hist.totals.mao_obra;
console.log(`Σ meses total: R$ ${histMonthlySum.toFixed(2)} (delta totais: ${(histMonthlySum - hist.totals.total).toFixed(2)})`);
console.log(`EQ+INS+MO = total: ${Math.abs(histPartsSum - hist.totals.total) < 0.02 ? "SIM" : "NÃO"}`);

if (hist.months.length > 0) {
  console.log("Amostra mês 0:", hist.months[0]);
}

const missingCpu = services.filter((s) => !compositions.has(s.row_id));
if (missingCpu.length) {
  console.log(`\nServiços SEM CPU (${missingCpu.length}):`);
  for (const s of missingCpu) {
    console.log(`  ${s.code} ${s.source_code} — R$ ${(s.total_effective ?? s.total_price ?? 0).toFixed(2)}`);
  }
}

console.log("\n=== FIM ===");
