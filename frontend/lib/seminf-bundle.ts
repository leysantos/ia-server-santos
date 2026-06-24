/** Detecção inteligente das 3 planilhas DP/SEMINF em pastas com muitos arquivos. */

const MONTHS_PT: Record<string, number> = {
  janeiro: 1,
  jan: 1,
  fevereiro: 2,
  fev: 2,
  marco: 3,
  março: 3,
  marc: 3,
  abril: 4,
  abr: 4,
  maio: 5,
  mai: 5,
  junho: 6,
  jun: 6,
  julho: 7,
  jul: 7,
  agosto: 8,
  ago: 8,
  setembro: 9,
  set: 9,
  outubro: 10,
  out: 10,
  novembro: 11,
  nov: 11,
  dezembro: 12,
  dez: 12,
};

const SPREADSHEET_EXT = /\.(xlsm|xlsx|xls)$/i;
const IGNORE_EXT = /\.(identifier|tmp|bak|download)$/i;

export type SeminfBundleFiles = {
  closed: File;
  openComd: File;
  openSemd: File;
};

export type SeminfBundleDetection = {
  folderName: string;
  files: SeminfBundleFiles;
  period: { year: number; month: number };
};

/** composição → composicao, preços → precos (sem acentos/separadores). */
export function normalizeFilenameToken(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[_\-\s.]+/g, "");
}

export function parseSeminfPeriodFromFilename(filename: string): { year: number; month: number } | null {
  const normalized = filename
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  const yearMatch = normalized.match(/20\d{2}/);
  if (!yearMatch) return null;
  const year = Number(yearMatch[0]);
  let month: number | null = null;
  for (const [token, num] of Object.entries(MONTHS_PT)) {
    const tokenNorm = token.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    if (normalized.includes(tokenNorm)) {
      month = num;
      break;
    }
  }
  if (!month) return null;
  return { year, month };
}

function basename(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

function isIgnoredFile(name: string): boolean {
  return IGNORE_EXT.test(name.toLowerCase());
}

function isClosedPriceFile(name: string): boolean {
  const stem = normalizeFilenameToken(name.replace(SPREADSHEET_EXT, ""));
  return stem.includes("tabela") && (stem.includes("preco") || stem.includes("precos"));
}

function isOpenComdFile(name: string): boolean {
  const stem = normalizeFilenameToken(name.replace(SPREADSHEET_EXT, ""));
  return stem.includes("composic") && stem.includes("seminf") && stem.includes("comd") && !stem.includes("semd");
}

function isOpenSemdFile(name: string): boolean {
  const stem = normalizeFilenameToken(name.replace(SPREADSHEET_EXT, ""));
  return stem.includes("composic") && stem.includes("seminf") && stem.includes("semd");
}

function periodScore(file: File, expectedYear: number, expectedMonth: number): number {
  const period = parseSeminfPeriodFromFilename(file.name);
  if (!period) return 0;
  if (period.year === expectedYear && period.month === expectedMonth) return 100;
  if (period.year === expectedYear) return 50;
  return 10;
}

function pickBest(candidates: File[], expectedYear: number, expectedMonth: number): File | null {
  if (candidates.length === 0) return null;
  return [...candidates].sort(
    (a, b) => periodScore(b, expectedYear, expectedMonth) - periodScore(a, expectedYear, expectedMonth)
  )[0];
}

function folderNameFromFileList(files: FileList): string {
  const first = files[0];
  if (!first) return "pasta";
  const rel = (first as File & { webkitRelativePath?: string }).webkitRelativePath || first.name;
  const parts = rel.replace(/\\/g, "/").split("/");
  return parts.length > 1 ? parts[0] : "pasta";
}

export function detectSeminfBundleFromFolder(
  fileList: FileList,
  expectedYear: number,
  expectedMonth: number
): SeminfBundleDetection | { error: string } {
  const spreadsheets = Array.from(fileList).filter(
    (f) => SPREADSHEET_EXT.test(f.name) && !isIgnoredFile(f.name)
  );

  const closedCandidates = spreadsheets.filter((f) => isClosedPriceFile(basename(f.name)));
  const comdCandidates = spreadsheets.filter((f) => isOpenComdFile(basename(f.name)));
  const semdCandidates = spreadsheets.filter((f) => isOpenSemdFile(basename(f.name)));

  const closed = pickBest(closedCandidates, expectedYear, expectedMonth);
  const openComd = pickBest(comdCandidates, expectedYear, expectedMonth);
  const openSemd = pickBest(semdCandidates, expectedYear, expectedMonth);

  const missing: string[] = [];
  if (!closed) missing.push("Tabela de Preço (tabela*preco*)");
  if (!openComd) missing.push("Composição SEMINF ComD");
  if (!openSemd) missing.push("Composição SEMINF SemD");

  if (missing.length > 0) {
    return {
      error: `Pasta incompleta para ${String(expectedMonth).padStart(2, "0")}/${expectedYear} — ${spreadsheets.length} planilha(s) analisada(s). Faltando: ${missing.join(", ")}.`,
    };
  }

  const files = { closed: closed!, openComd: openComd!, openSemd: openSemd! };
  const periods = [files.closed, files.openComd, files.openSemd]
    .map((f) => parseSeminfPeriodFromFilename(f.name))
    .filter((p): p is { year: number; month: number } => p !== null);

  if (periods.length === 3) {
    const mismatch = periods.find((p) => p.year !== expectedYear || p.month !== expectedMonth);
    if (mismatch) {
      return {
        error: `As planilhas são de ${String(mismatch.month).padStart(2, "0")}/${mismatch.year}, mas o período selecionado é ${String(expectedMonth).padStart(2, "0")}/${expectedYear}. Ajuste o mês/ano ou escolha outra pasta.`,
      };
    }
  }

  const period = periods[0] ?? { year: expectedYear, month: expectedMonth };
  return {
    folderName: folderNameFromFileList(fileList),
    files,
    period,
  };
}

/** Nome só do arquivo — evita path de subpasta no multipart (webkitdirectory). */
export function fileWithBasename(file: File): File {
  const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
  const fromPath = rel?.replace(/\\/g, "/").split("/").pop();
  const name = (fromPath || file.name).replace(/\\/g, "/").split("/").pop() || file.name;
  if (name === file.name) return file;
  return new File([file], name, { type: file.type, lastModified: file.lastModified });
}

export function seminfBundleFilesWithBasenames(files: SeminfBundleFiles): SeminfBundleFiles {
  return {
    closed: fileWithBasename(files.closed),
    openComd: fileWithBasename(files.openComd),
    openSemd: fileWithBasename(files.openSemd),
  };
}

export function formatSeminfBundleSummary(detection: SeminfBundleDetection): string {
  const { folderName, files, period } = detection;
  return `${folderName} — ${String(period.month).padStart(2, "0")}/${period.year}: ${files.closed.name}, ${files.openComd.name}, ${files.openSemd.name}`;
}
