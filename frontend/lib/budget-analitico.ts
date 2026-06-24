import type { BudgetPriceBaseSelection, BudgetRow, PriceBankReference } from "@/types/api";

export interface BudgetAnaliticoLine {
  row_id: string;
  wbs_code: string;
  composition_code: string;
  description: string;
  unit: string;
  quantity: number;
  unit_cost: number;
  unit_cost_semd: number;
  total_price: number;
  total_price_semd: number;
  source_base: string;
  base: BudgetPriceBaseSelection | null;
}

export interface AnaliticoServiceNode {
  service: BudgetRow;
  line: BudgetAnaliticoLine;
}

export interface AnaliticoGroupNode {
  group: BudgetRow;
  services: AnaliticoServiceNode[];
  subgroups: AnaliticoGroupNode[];
}

function normSource(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function isSeminfCompositionCode(code: string): boolean {
  return /\.seminf$/i.test((code || "").trim());
}

function isSeminfPriceBaseSource(source: string): boolean {
  const key = normSource(source);
  return key === "dpseminf" || key === "ppdseminf" || key === "seminf";
}

function findSeminfPriceBase(
  priceBases: BudgetPriceBaseSelection[]
): BudgetPriceBaseSelection | null {
  const enabled = priceBases.filter((b) => b.enabled && b.reference);
  return enabled.find((b) => isSeminfPriceBaseSource(b.source)) ?? null;
}

function isSeminfBankReference(ref: PriceBankReference): boolean {
  return (
    isSeminfPriceBaseSource(ref.source || "") || /DP-SEMINF|BR-SEMINF/i.test(ref.reference || "")
  );
}

export function parseReferenceMonthFromBasePreco(
  basePreco?: string
): { year: number; month: number } | null {
  const text = (basePreco || "").trim();
  if (!text) return null;
  const labeled =
    text.match(/(?:M[eê]s de Refer[eê]ncia|Refer[eê]ncia)\s*:\s*(\d{1,2})\/(\d{4})/i) ??
    text.match(/\b(\d{1,2})\/(\d{4})\b/);
  if (!labeled) return null;
  const month = Number(labeled[1]);
  const year = Number(labeled[2]);
  if (month < 1 || month > 12 || year < 2000) return null;
  return { year, month };
}

function buildSeminfSelectionFromReferences(
  bankReferences: PriceBankReference[],
  opts: { priceBases: BudgetPriceBaseSelection[]; basePreco?: string }
): BudgetPriceBaseSelection | null {
  const seminfRefs = bankReferences.filter(isSeminfBankReference);
  if (seminfRefs.length === 0) return null;

  const period = parseReferenceMonthFromBasePreco(opts.basePreco);
  let refRow: PriceBankReference | undefined;
  if (period) {
    const target = `BR-DP-SEMINF-${period.year}-${String(period.month).padStart(2, "0")}`;
    refRow = seminfRefs.find((r) => r.reference.toUpperCase() === target.toUpperCase());
  }
  if (!refRow) {
    refRow = [...seminfRefs].sort((a, b) => b.reference.localeCompare(a.reference))[0];
  }

  const ufHint =
    opts.priceBases.find((b) => b.enabled && b.uf)?.uf || refRow.default_uf || "AM";

  const source = (refRow.source || "dp_seminf").toLowerCase();
  return {
    source,
    label: refRow.label || "DP/SEMINF",
    enabled: true,
    uf: ufHint,
    reference: refRow.reference,
  };
}

export interface ResolvePriceBaseOptions {
  bankReferences?: PriceBankReference[];
  basePreco?: string;
}

export function resolvePriceBaseForRow(
  row: BudgetRow,
  priceBases: BudgetPriceBaseSelection[],
  options: ResolvePriceBaseOptions = {}
): BudgetPriceBaseSelection | null {
  const enabled = priceBases.filter((b) => b.enabled && b.reference);
  const bankReferences = options.bankReferences ?? [];
  const compositionCode = (row.source_code || row.code || "").trim();

  // Códigos regionais (*.SEMINF) existem só no banco DP/SEMINF — nunca consultar SINAPI Caixa.
  if (isSeminfCompositionCode(compositionCode)) {
    const fromSession = findSeminfPriceBase(priceBases);
    if (fromSession) return fromSession;
    const fromBank = buildSeminfSelectionFromReferences(bankReferences, {
      priceBases,
      basePreco: options.basePreco,
    });
    if (fromBank) return fromBank;
    return null;
  }

  if (enabled.length === 0) return null;

  const raw = (row.source_base || "").trim();
  if (!raw) return enabled[0];

  const key = normSource(raw);
  if (isSeminfPriceBaseSource(key)) {
    return findSeminfPriceBase(priceBases) ?? buildSeminfSelectionFromReferences(bankReferences, {
      priceBases,
      basePreco: options.basePreco,
    }) ?? enabled[0];
  }

  const exact = enabled.find((b) => normSource(b.source) === key || normSource(b.label) === key);
  if (exact) return exact;

  const partial = enabled.find(
    (b) => key.includes(normSource(b.source)) || normSource(b.source).includes(key)
  );
  return partial ?? enabled[0];
}

export function lineFromService(
  row: BudgetRow,
  priceBases: BudgetPriceBaseSelection[] = [],
  options: ResolvePriceBaseOptions = {}
): BudgetAnaliticoLine | null {
  if (row.row_type !== "S" || row.is_memory_row) return null;
  const compositionCode = (row.source_code || row.code || "").trim();
  if (!compositionCode) return null;

  const base = resolvePriceBaseForRow(row, priceBases, options);

  return {
    row_id: row.row_id,
    wbs_code: row.code,
    composition_code: compositionCode,
    description: row.name,
    unit: row.unit,
    quantity: row.quantity,
    unit_cost: row.unit_cost,
    unit_cost_semd: row.unit_cost_semd ?? row.unit_cost,
    total_price: row.total_price,
    total_price_semd: row.total_price_semd ?? row.total_price,
    source_base: row.source_base || "",
    base,
  };
}

export function extractBudgetAnaliticoLines(
  rows: BudgetRow[],
  priceBases: BudgetPriceBaseSelection[] = [],
  options: ResolvePriceBaseOptions = {}
): BudgetAnaliticoLine[] {
  return rows
    .filter((row) => row.row_type === "S" && !row.is_memory_row)
    .map((row) => lineFromService(row, priceBases, options))
    .filter((line): line is BudgetAnaliticoLine => line !== null);
}

function directServices(rows: BudgetRow[], groupCode: string): BudgetRow[] {
  return rows.filter(
    (r) => r.row_type === "S" && !r.is_memory_row && r.parent_code === groupCode
  );
}

function subetapas(rows: BudgetRow[], parentCode: string): BudgetRow[] {
  return rows.filter((r) => r.row_type === "SUB-ETAPA" && r.parent_code === parentCode);
}

function matchesFilter(line: BudgetAnaliticoLine, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    line.wbs_code.toLowerCase().includes(q) ||
    line.composition_code.toLowerCase().includes(q) ||
    line.description.toLowerCase().includes(q)
  );
}

export function buildAnaliticoTree(
  rows: BudgetRow[],
  priceBases: BudgetPriceBaseSelection[] = [],
  query = "",
  options: ResolvePriceBaseOptions = {}
): AnaliticoGroupNode[] {
  const etapas = rows.filter((r) => r.row_type === "ETAPA" && r.level === 0);

  const buildGroup = (group: BudgetRow): AnaliticoGroupNode | null => {
    const services = directServices(rows, group.code)
      .map((service) => {
        const line = lineFromService(service, priceBases, options);
        return line && matchesFilter(line, query) ? { service, line } : null;
      })
      .filter((node): node is AnaliticoServiceNode => node !== null);

    const subgroups = subetapas(rows, group.code)
      .map(buildGroup)
      .filter((node): node is AnaliticoGroupNode => node !== null);

    if (services.length === 0 && subgroups.length === 0) return null;
    return { group, services, subgroups };
  };

  return etapas
    .map(buildGroup)
    .filter((node): node is AnaliticoGroupNode => node !== null);
}

export function filterAnaliticoLines(
  lines: BudgetAnaliticoLine[],
  query: string
): BudgetAnaliticoLine[] {
  const q = query.trim().toLowerCase();
  if (!q) return lines;
  return lines.filter(
    (line) =>
      line.wbs_code.toLowerCase().includes(q) ||
      line.composition_code.toLowerCase().includes(q) ||
      line.description.toLowerCase().includes(q)
  );
}

export function countAnaliticoServices(node: AnaliticoGroupNode): number {
  return (
    node.services.length + node.subgroups.reduce((sum, sub) => sum + countAnaliticoServices(sub), 0)
  );
}

export function flattenAnaliticoTree(tree: AnaliticoGroupNode[]): AnaliticoServiceNode[] {
  const out: AnaliticoServiceNode[] = [];
  for (const node of tree) {
    out.push(...node.services);
    out.push(...flattenAnaliticoTree(node.subgroups));
  }
  return out;
}

export function formatBudgetBasesSummary(priceBases: BudgetPriceBaseSelection[]): string {
  const enabled = priceBases.filter((b) => b.enabled && b.reference);
  if (enabled.length === 0) return "Nenhuma base configurada";
  return enabled
    .map((b) => `${b.label} ${b.uf} · ${b.reference.replace(/^BR-/, "").replace(/-/g, "/")}`)
    .join(" · ");
}
