import type { OpenCompositionDetail } from "@/types/api";

export const CPU_ITEM_TYPE_LABELS: Record<string, string> = {
  mao_obra: "Mão de obra",
  insumo: "Material",
  equipamento: "Equipamento",
  composicao: "Composição",
  atividade: "Atividade auxiliar",
  tempo_fixo: "Tempo fixo",
  transporte: "Transporte",
  fic: "FIC",
};

export function cpuItemTypeLabel(itemType: string): string {
  return CPU_ITEM_TYPE_LABELS[itemType] ?? itemType.replace(/_/g, " ");
}

export function formatBrl(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function previewTotalSemd(comp: OpenCompositionDetail): number {
  return (
    comp.total_price_sem ??
    comp.items.reduce((sum, item) => sum + (item.partial_cost_sem ?? item.partial_cost), 0)
  );
}

export function formatPctAs(value: number | undefined): string {
  if (value == null || value <= 0) return "—";
  return `${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;
}

export function formatLaborChargePct(value: number | undefined): string {
  if (value == null || value <= 0) return "—";
  return `${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

export function previewPctAs(comp: OpenCompositionDetail, mode: "comd" | "semd"): number | undefined {
  return mode === "semd" ? comp.pct_as_semd : comp.pct_as_comd;
}
