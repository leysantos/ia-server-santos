import type { OpenCompositionItem } from "@/types/api";

export type ResourceCategory = "equipamento" | "insumo" | "mao_obra";

const LABOR_UNITS = new Set(["H", "MES", "MÊS", "MÊS.", "MES."]);

const LABOR_DESC_MARKERS = [
  "mensalista",
  "horista",
  "mão de obra",
  "mao de obra",
  " pedreiro",
  " servente",
  " encarregado",
  " engenheiro",
  " almoxarife",
  " eletricista",
  " carpinteiro",
  " armador",
  "profissional",
  "operário",
  "operario",
  " mestre de obras",
  " ajudante",
  " guincheiro",
] as const;

const INDIRECT_MO_PREFIXES = [
  "epi ",
  "epi-",
  "ferramentas ",
  "ferramentas-",
  "seguro ",
  "seguro-",
  "exames ",
  "exames-",
  "alimentacao ",
  "alimentacao-",
  "transporte ",
  "transporte-",
  "locacao ",
  "locacao-",
  "uniforme",
  "cesta basica",
  "vale transporte",
  "vale alimentacao",
  "plano de saude",
  "medicina ocupacional",
  "gratificacao",
  "bonus ",
] as const;

const INDIRECT_MO_SUBSTRINGS = [
  "locacao de container",
  "locacao container",
  "aluguel de container",
] as const;

const DIRECT_LABOR_ROLE_MARKERS = [
  "pedreiro",
  "servente",
  "encarregado",
  "engenheiro",
  "almoxarife",
  "eletricista",
  "vigia",
  "mecanico",
  "carpinteiro",
  "armador",
  "soldador",
  "montador",
  "operador",
  "guindaste",
  "guincheiro",
  "mestre de obra",
  "mestre obra",
  "tecnico de seguranca",
  "técnico de segurança",
  "oficial de producao",
  "oficial de produção",
  "topografo",
  "topógrafo",
  "sondador",
  "pre-marcador",
  "pre marcador",
  "premarcador",
  "gesseiro",
  "pintor",
  "serralheiro",
  "encanador",
  "profissional",
  "operario",
  "operário",
  "borracheiro",
  "rigger",
  "ajudante",
  "auxiliar de eletricista",
  "auxiliar de mecanico",
  "auxiliar de montagem",
  "auxiliar de sondagem",
  "auxiliar topografico",
  "auxiliar topográfico",
] as const;

export function normalizeResourceText(value: string): string {
  let text = (value || "").toLowerCase();
  text = text
    .replace(/á|à|ã/g, "a")
    .replace(/é|ê/g, "e")
    .replace(/í/g, "i")
    .replace(/ó|ô|õ/g, "o")
    .replace(/ú/g, "u")
    .replace(/ç/g, "c");
  return text.replace(/\s+/g, " ").trim();
}

function isHourUnit(unit: string): boolean {
  const u = (unit || "").trim().toUpperCase();
  return u === "H" || u === "HH" || u === "CH" || u === "H/H" || u.includes("HORA");
}

export function isIndirectMoCharge(description: string): boolean {
  const norm = normalizeResourceText(description);
  if (!norm) return false;

  if (INDIRECT_MO_PREFIXES.some((prefix) => norm.startsWith(prefix))) return true;
  if (INDIRECT_MO_SUBSTRINGS.some((sub) => norm.includes(sub))) return true;

  if (norm.includes("coletado caixa") && norm.includes("encargos complementares")) {
    if (!isDirectLaborRole(description)) return true;
  }

  return false;
}

export function isDirectLaborRole(description: string): boolean {
  const norm = normalizeResourceText(description);
  if (!norm) return false;
  return DIRECT_LABOR_ROLE_MARKERS.some((marker) => norm.includes(marker));
}

/** Profissional de obra — entra no histograma MO direta (exclui EPI, transporte, etc.). */
export function isHistogramDirectLabor(item: OpenCompositionItem): boolean {
  if (resolveResourceCategory(item) !== "mao_obra") return false;

  const desc = String(item.description || "");
  if (isIndirectMoCharge(desc)) return false;

  const unit = String(item.unit || "");
  if (isHourUnit(unit)) return true;

  return isDirectLaborRole(desc);
}

export function isLaborDescriptor(description: string, unit: string): boolean {
  const unitKey = (unit || "").trim().toUpperCase().replace(/\./g, "");
  if (LABOR_UNITS.has(unitKey)) return true;
  const blob = (description || "").toLowerCase();
  if (blob.includes("(mensalista)") || blob.includes("(horista)")) return true;
  return LABOR_DESC_MARKERS.some((marker) => blob.includes(marker));
}

function classificacaoToCategory(classificacao: string): ResourceCategory | null {
  const key = (classificacao || "").trim().toLowerCase();
  if (!key) return null;
  if (key.includes("mao") && key.includes("obra")) return "mao_obra";
  if (key === "material" || key === "materiais") return "insumo";
  if (key.includes("equip")) return "equipamento";
  if (key.includes("servi")) return null;
  return null;
}

/** Resolve categoria econômica de um item de CPU (espelha backend). */
export function resolveResourceCategory(item: OpenCompositionItem): ResourceCategory | null {
  const itemType = String(item.item_type || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_");
  const desc = String(item.description || "");
  const unit = String(item.unit || "");

  if (itemType === "composicao") return null;

  const fromClass = classificacaoToCategory(String(item.classificacao || ""));
  if (fromClass === "mao_obra") return "mao_obra";
  if (fromClass === "equipamento") return "equipamento";
  if (fromClass === "insumo") {
    if (isLaborDescriptor(desc, unit)) return "mao_obra";
    return "insumo";
  }

  if (isLaborDescriptor(desc, unit)) return "mao_obra";

  if (itemType === "equipamento") return "equipamento";
  if (itemType === "mao_obra" || itemType === "maodeobra") return "mao_obra";
  if (itemType === "insumo" || itemType === "material") return "insumo";

  return null;
}
