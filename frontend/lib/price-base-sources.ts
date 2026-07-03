import type { BudgetPriceBaseSelection, PriceBankReference } from "@/types/api";
import {
  sicroReferenceMatchesUf,
} from "@/lib/sicro-links";

export const SOURCE_LABELS: Record<string, string> = {
  sinapi: "SINAPI",
  tcpo: "TCPO",
  orse: "ORSE",
  dp_seminf: "DP/SEMINF",
  ppd_seminf: "PP/SEMINF",
  cicro: "SICRO/SICRO",
};

export function sourceKey(ref: Pick<PriceBankReference, "source" | "reference">): string {
  return (ref.source || "sinapi").toLowerCase();
}

export function isSeminfSource(source: string): boolean {
  const s = source.toLowerCase();
  return s === "dp_seminf" || s === "ppd_seminf";
}

export function sourceLabel(name: string, references: PriceBankReference[]): string {
  if (SOURCE_LABELS[name]) return SOURCE_LABELS[name];
  const ref = references.find((r) => sourceKey(r) === name);
  if (ref?.source) {
    const key = sourceKey({ ...ref, source: ref.source });
    if (SOURCE_LABELS[key]) return SOURCE_LABELS[key];
  }
  return name.replace(/_/g, " ").toUpperCase();
}

export function refsForSource(
  source: string,
  uf: string,
  references: PriceBankReference[]
): PriceBankReference[] {
  if (source === "cicro") {
    return references.filter(
      (r) =>
        (sourceKey(r) === "cicro" || r.reference.toUpperCase().includes("SICRO")) &&
        sicroReferenceMatchesUf(r.reference, uf)
    );
  }
  if (isSeminfSource(source)) {
    return references.filter((r) => isSeminfSource(sourceKey(r)));
  }
  return references.filter((r) => sourceKey(r) === source);
}

export function sourceOptionsFromReferences(
  references: PriceBankReference[]
): Array<{ name: string; label: string }> {
  const names = new Set<string>();
  for (const r of references) {
    names.add(sourceKey(r));
  }
  return Array.from(names)
    .map((name) => ({
      name,
      label: sourceLabel(name, references),
    }))
    .sort((a, b) => a.label.localeCompare(b.label, "pt-BR"));
}

export function defaultUfForSource(
  source: string,
  references: PriceBankReference[],
  ufHint = "SP"
): string {
  const refs = refsForSource(source, ufHint, references);
  const fromRef = refs[0]?.default_uf;
  if (fromRef) return fromRef.toUpperCase();
  if (source === "cicro" || isSeminfSource(source)) return "AM";
  if (source === "orse") return "SE";
  return "SP";
}

export function buildPriceBaseSelection(
  source: string,
  reference: string,
  uf: string,
  references: PriceBankReference[]
): BudgetPriceBaseSelection {
  return {
    source,
    label: sourceLabel(source, references),
    enabled: true,
    uf: uf.toUpperCase(),
    reference,
  };
}

/** Inclui ou atualiza a base usada na busca/lançamento de CPU no orçamento. */
export function upsertPriceBaseSelection(
  priceBases: BudgetPriceBaseSelection[],
  selection: BudgetPriceBaseSelection
): BudgetPriceBaseSelection[] {
  const current = priceBases.find((b) => b.enabled && b.source === selection.source);
  if (
    current &&
    current.reference === selection.reference &&
    current.uf.toUpperCase() === selection.uf.toUpperCase()
  ) {
    return priceBases;
  }
  return [...priceBases.filter((b) => b.source !== selection.source), selection];
}

export function priceBasesEqual(
  a: BudgetPriceBaseSelection[],
  b: BudgetPriceBaseSelection[]
): boolean {
  if (a.length !== b.length) return false;
  const norm = (rows: BudgetPriceBaseSelection[]) =>
    [...rows]
      .map((r) => `${r.source}|${r.reference}|${r.uf}|${r.enabled}`)
      .sort()
      .join(";");
  return norm(a) === norm(b);
}
