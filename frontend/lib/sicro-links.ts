/** Portal DNIT SICRO e mapa região → UF. */

export const SICRO_PORTAL_URL =
  "https://www.gov.br/dnit/pt-br/assuntos/planejamento-e-pesquisa/custos-referenciais/sistemas-de-custos/sicro/relatorios/relatorios-sicro";

export const SICRO_QUARTER_MONTHS = [1, 4, 7, 10] as const;

export const SICRO_REGIONS: Array<{
  id: string;
  label: string;
  ufs: readonly string[];
}> = [
  { id: "norte", label: "Norte", ufs: ["AC", "AM", "AP", "PA", "RO", "RR", "TO"] },
  {
    id: "nordeste",
    label: "Nordeste",
    ufs: ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
  },
  { id: "centro-oeste", label: "Centro-Oeste", ufs: ["DF", "GO", "MT", "MS"] },
  { id: "sudeste", label: "Sudeste", ufs: ["ES", "MG", "RJ", "SP"] },
  { id: "sul", label: "Sul", ufs: ["PR", "RS", "SC"] },
];

const UF_TO_REGION = new Map<string, string>(
  SICRO_REGIONS.flatMap((r) => r.ufs.map((uf) => [uf, r.id] as const))
);

export function sicroDefaultPeriod(): { year: number; month: number } {
  const now = new Date();
  let year = now.getFullYear();
  let month = 1;
  for (const m of [...SICRO_QUARTER_MONTHS].reverse()) {
    if (now.getMonth() + 1 >= m) {
      month = m;
      break;
    }
  }
  if (month === 1 && now.getMonth() + 1 < 1) {
    year -= 1;
    month = 10;
  }
  return { year, month };
}

export function sicroRegionForUf(uf: string): string | undefined {
  return UF_TO_REGION.get(uf.toUpperCase());
}

export function sicroUfsForRegion(regionId: string): readonly string[] {
  if (!regionId || regionId === "all") {
    return SICRO_REGIONS.flatMap((r) => r.ufs);
  }
  return SICRO_REGIONS.find((r) => r.id === regionId)?.ufs ?? [];
}

export function sicroReferenceMatchesUf(reference: string, uf: string): boolean {
  const u = uf.toUpperCase();
  const ref = reference.toUpperCase();
  return ref.includes(`-SICRO-${u}-`) || ref.startsWith(`BR-SICRO-${u}-`);
}
