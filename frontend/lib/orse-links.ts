/** URLs e helpers — ORSE (Sergipe / CEHOP). */

export const ORSE_PORTAL_URL = "https://orse.cehop.se.gov.br/downloads.asp?base=orse";

export function orseDefaultPeriod(): { year: number; month: number } {
  const now = new Date();
  if (now.getMonth() === 0) {
    return { year: now.getFullYear() - 1, month: 12 };
  }
  return { year: now.getFullYear(), month: now.getMonth() };
}

export function orseMonthlyDownloadUrl(year: number, month: number): string {
  const yyyymm = `${year}${String(month).padStart(2, "0")}01`;
  return `https://orse.cehop.se.gov.br/downloads/${yyyymm}-00.ORSE`;
}

export function orseReferenceKey(year: number, month: number): string {
  return `BR-ORSE-${year}-${String(month).padStart(2, "0")}`;
}

export function parseOrseRefPeriod(reference: string): { year: number; month: number } | null {
  const m = reference.match(/^BR-ORSE-(\d{4})-(\d{2})$/i);
  if (!m) return null;
  return { year: Number(m[1]), month: Number(m[2]) };
}

export function formatOrsePeriodLabel(year: number, month: number): string {
  return `${String(month).padStart(2, "0")}/${year}`;
}
