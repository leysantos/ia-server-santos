/** UFs brasileiras — ordem alfabética (padrão SINAPI). */
export const BRAZIL_UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
  "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
] as const;

export type BrazilUf = (typeof BRAZIL_UFS)[number];

export function referenceLabelFromKey(reference: string): string {
  const m = reference.match(/^BR-(\d{4})-(\d{2})$/i);
  if (m) return `${m[2]}/${m[1]}`;
  return reference;
}
