export type LancarPrecosTabId =
  | "lancar_precos"
  | "historico"
  | "dados"
  | "etapas"
  | "ppd"
  | "analitico"
  | "memoria"
  | "cronograma"
  | "curva_abc"
  | "curva_s"
  | "histograma"
  | "especificacao";

const LANCAR_PRECOS_JOB_KEY = "iaserver.lancar-precos.jobId";
const LANCAR_PRECOS_TAB_KEY = "iaserver.lancar-precos.lastTab";

const TAB_IDS = new Set<LancarPrecosTabId>([
  "lancar_precos",
  "historico",
  "dados",
  "etapas",
  "ppd",
  "analitico",
  "memoria",
  "cronograma",
  "curva_abc",
  "curva_s",
  "histograma",
  "especificacao",
]);

export function parseLancarPrecosTab(value: string | null): LancarPrecosTabId {
  if (value && TAB_IDS.has(value as LancarPrecosTabId)) {
    return value as LancarPrecosTabId;
  }
  if (typeof window !== "undefined") {
    const last = sessionStorage.getItem(LANCAR_PRECOS_TAB_KEY);
    if (last && TAB_IDS.has(last as LancarPrecosTabId)) {
      return last as LancarPrecosTabId;
    }
  }
  return "lancar_precos";
}

export function persistLancarPrecosJob(jobId: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (!jobId) sessionStorage.removeItem(LANCAR_PRECOS_JOB_KEY);
    else sessionStorage.setItem(LANCAR_PRECOS_JOB_KEY, jobId);
  } catch {
    /* quota */
  }
}

export function readLancarPrecosJob(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(LANCAR_PRECOS_JOB_KEY);
}

export function persistLancarPrecosTab(tab: LancarPrecosTabId): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(LANCAR_PRECOS_TAB_KEY, tab);
  } catch {
    /* quota */
  }
}

export function buildLancarPrecosUrl(jobId: string | null, tab: LancarPrecosTabId): string {
  const params = new URLSearchParams();
  if (jobId) params.set("job", jobId);
  if (tab !== "lancar_precos" && tab !== "historico") params.set("tab", tab);
  const qs = params.toString();
  return qs ? `/budget/lancar-precos?${qs}` : "/budget/lancar-precos";
}
