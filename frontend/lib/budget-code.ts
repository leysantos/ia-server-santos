/** Gera código de orçamento: ORC0001-MM/AAAA-INICIAIS */

const ORC_PREFIX_RE = /^ORC(\d+)/i;

export function parseOrcSequence(code: string): number | null {
  const m = ORC_PREFIX_RE.exec(code.trim());
  return m ? parseInt(m[1], 10) : null;
}

export function nextOrcSequence(codes: string[]): number {
  let max = 0;
  for (const code of codes) {
    const n = parseOrcSequence(code);
    if (n !== null && n > max) max = n;
  }
  return max + 1;
}

export function companyInitials(empresa: string): string {
  const words = empresa
    .trim()
    .split(/\s+/)
    .filter((w) => w.length > 0);
  if (words.length === 0) return "EMP";
  if (words.length === 1) {
    const w = words[0].replace(/[^a-zA-ZÀ-ÿ0-9]/g, "");
    return (w.slice(0, 3) || "EMP").toUpperCase();
  }
  return words
    .map((w) => w.replace(/[^a-zA-ZÀ-ÿ]/g, "").charAt(0))
    .join("")
    .slice(0, 4)
    .toUpperCase();
}

export function currentMonthYear(date = new Date()): string {
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  return `${mm}/${date.getFullYear()}`;
}

export function formatBudgetCode(sequence: number, empresa: string, date = new Date()): string {
  const seq = `ORC${String(sequence).padStart(4, "0")}`;
  return `${seq}-${currentMonthYear(date)}-${companyInitials(empresa)}`;
}

/** Mantém o número sequencial se já existir no código atual; senão usa o próximo livre. */
export function buildBudgetCode(
  existingCodes: string[],
  empresa: string,
  currentCode?: string,
  date = new Date()
): string {
  const kept = currentCode ? parseOrcSequence(currentCode) : null;
  const seq = kept ?? nextOrcSequence(existingCodes);
  return formatBudgetCode(seq, empresa, date);
}
