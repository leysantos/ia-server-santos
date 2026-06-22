/** Links oficiais SINAPI (Caixa) — evitar default.aspx (loop de redirect). */

export const SINAPI_PORTAL = "https://www.caixa.gov.br/sinapi";

export const SINAPI_DOWNLOADS_BASE =
  "https://www.caixa.gov.br/site/Paginas/downloads.aspx";

/** Relatórios mensais nacionais (formato ZIP/XLSX 2025+) — categoria no portal Caixa. */
export const SINAPI_NATIONAL_CATEGORIA = 888;

export function sinapiNationalDownloadsUrl(): string {
  return `${SINAPI_DOWNLOADS_BASE}#categoria_${SINAPI_NATIONAL_CATEGORIA}`;
}

/** Formato 2025+: ZIP nacional com planilha Referência (todas UFs). */
export const SINAPI_NATIONAL_BASE =
  "https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais";

export const SINAPI_SUMARIO_MIRROR =
  "https://cesarep.github.io/sumario-sinapi/#relatorios-mensais";

/** Formato 2025+: ZIP nacional com planilha Referência (todas UFs). */
export function sinapiNationalZipUrl(year: number, month: number): string {
  return `${SINAPI_NATIONAL_BASE}/SINAPI-${year}-${String(month).padStart(2, "0")}-formato-xlsx.zip`;
}

/** Mês de referência padrão: mês anterior ao calendário. */
export function sinapiDefaultPeriod(): { year: number; month: number } {
  const now = new Date();
  if (now.getMonth() === 0) {
    return { year: now.getFullYear() - 1, month: 12 };
  }
  return { year: now.getFullYear(), month: now.getMonth() };
}

/** Categoria downloads.aspx por UF (espelho do sumário oficial SINAPI). */
const SINAPI_UF_CATEGORIA: Record<string, number> = {
  AC: 638,
  AL: 639,
  AM: 640,
  AP: 641,
  BA: 642,
  CE: 643,
  DF: 644,
  ES: 645,
  GO: 646,
  MA: 647,
  MG: 648,
  MS: 649,
  MT: 650,
  PA: 651,
  PB: 652,
  PE: 653,
  PI: 654,
  PR: 655,
  RJ: 656,
  RN: 657,
  RO: 658,
  RR: 659,
  RS: 660,
  TO: 661,
  SC: 662,
  SE: 663,
  SP: 664,
};

export function sinapiDownloadsUrl(uf: string): string {
  const code = uf.toUpperCase();
  const cat = SINAPI_UF_CATEGORIA[code];
  if (!cat) return SINAPI_PORTAL;
  return `${SINAPI_DOWNLOADS_BASE}#categoria_${cat}`;
}

/** Abre link externo (funciona melhor em webviews/Electron do que href puro). */
export function openExternalUrl(url: string): void {
  window.open(url, "_blank", "noopener,noreferrer");
}
