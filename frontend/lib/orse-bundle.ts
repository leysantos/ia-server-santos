import { normalizeFilenameToken } from "@/lib/seminf-bundle";

const SPREADSHEET_EXT = new Set([".xlsm", ".xlsx", ".xls", ".csv"]);

const FOREIGN_STEM_MARKERS = [
  "seminf",
  "semiinf",
  "ppdseminf",
  "dpseminf",
  "tabelapreco",
  "modmcor",
  "mcor",
  "nivel",
  "sinapi",
  "sicro",
  "tcpo",
];

function isSpreadsheet(name: string): boolean {
  const lower = name.toLowerCase();
  const dot = lower.lastIndexOf(".");
  if (dot < 0) return false;
  return SPREADSHEET_EXT.has(lower.slice(dot));
}

function stemNorm(name: string): string {
  const base = name.replace(/\.[^.]+$/, "");
  return normalizeFilenameToken(base);
}

export function isForeignPriceBaseName(name: string): boolean {
  const stem = stemNorm(name);
  if (FOREIGN_STEM_MARKERS.some((m) => stem.includes(m))) return true;
  if (stem.includes("composic") && (stem.includes("comd") || stem.includes("semd"))) return true;
  return false;
}

export function isOrseInsumosName(name: string): boolean {
  if (isForeignPriceBaseName(name)) return false;
  return stemNorm(name).includes("insumo");
}

export function isOrseComposicoesName(name: string): boolean {
  if (isForeignPriceBaseName(name)) return false;
  const stem = stemNorm(name);
  if (stem.includes("insumo")) return false;
  return ["composic", "servic", "cpu", "precounit", "orse"].some((t) => stem.includes(t));
}

export function isOrseAnaliticoName(name: string): boolean {
  if (isForeignPriceBaseName(name)) return false;
  const stem = stemNorm(name);
  return stem.includes("analit") || stem.includes("estrutur");
}

export type OrseBundleDetection =
  | {
      files: { composicoes: File; insumos: File; analitico: File };
      folderName?: string;
    }
  | { error: string };

export function detectOrseBundleFromFolder(fileList: FileList): OrseBundleDetection {
  const files = Array.from(fileList).filter((f) => isSpreadsheet(f.name) && !isForeignPriceBaseName(f.name));
  const foreign = Array.from(fileList).filter((f) => isSpreadsheet(f.name) && isForeignPriceBaseName(f.name));

  if (files.length === 0) {
    if (foreign.length > 0) {
      const seen = foreign
        .slice(0, 6)
        .map((f) => f.name)
        .join(", ");
      return {
        error: `Pasta contém planilhas SEMINF/SINAPI/PPD, não exports ORSE. Exporte do ORSE 2 (Relatórios → Cadastrais). Ignorados: ${seen}`,
      };
    }
    return { error: "Nenhuma planilha (.xlsx/.xls/.csv) na pasta selecionada." };
  }

  const composicoes = files.find((f) => isOrseComposicoesName(f.name));
  const insumos = files.find((f) => isOrseInsumosName(f.name));
  const analitico = files.find((f) => isOrseAnaliticoName(f.name));

  if (!composicoes) {
    const seen = files
      .slice(0, 6)
      .map((f) => f.name)
      .join(", ");
    return {
      error: `Planilha de composições/serviços não encontrada. Exporte do ORSE 2 (Relatórios → Cadastrais). Vistos: ${seen}`,
    };
  }

  if (!insumos) {
    return {
      error:
        "Planilha de Insumos não encontrada. No ORSE 2 exporte Relatórios → Cadastrais → Insumos (Excel) na mesma pasta.",
    };
  }

  if (!analitico) {
    return {
      error:
        "Planilha Analítico de Composições não encontrada. No ORSE 2 exporte Relatórios → Cadastrais → Analítico (Excel) para importar CPUs abertas.",
    };
  }

  const folderName = files[0]?.webkitRelativePath?.split("/")[0];
  return {
    files: {
      composicoes,
      insumos,
      analitico,
    },
    folderName,
  };
}

export function formatOrseBundleSummary(detection: Exclude<OrseBundleDetection, { error: string }>): string {
  const parts = [
    detection.files.composicoes.name,
    detection.files.insumos.name,
    detection.files.analitico.name,
  ];
  const prefix = detection.folderName ? `${detection.folderName}: ` : "";
  return `${prefix}${parts.join(" · ")}`;
}
