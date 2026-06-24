import type { HealthResponse } from "@/types/api";

export interface ModelsStatusDisplay {
  /** Texto após o prefixo WSL (modelos separados por ·). */
  modelsText: string;
}

/** Ordem de exibição no rótulo WSL (alinhada ao backend). */
const MODEL_DISPLAY_PRIORITY = [
  "qwen3.6",
  "gemma4",
  "deepseek-r1",
  "qwen3-coder",
  "qwen3:14",
  "qwen3:8",
  "gemma3",
  "qwen2.5-coder",
  "mistral",
  "deepseek-coder",
  "phi3",
] as const;

function modelDisplaySortKey(name: string): [number, number, string] {
  const lower = name.toLowerCase();
  const idx = MODEL_DISPLAY_PRIORITY.findIndex((token) => lower.includes(token));
  if (idx >= 0) return [0, idx, lower];
  return [1, 0, lower];
}

function sortModelNames(names: string[]): string[] {
  return [...names].sort((a, b) => {
    const ka = modelDisplaySortKey(a);
    const kb = modelDisplaySortKey(b);
    if (ka[0] !== kb[0]) return ka[0] - kb[0];
    if (ka[1] !== kb[1]) return ka[1] - kb[1];
    return ka[2].localeCompare(kb[2]);
  });
}

function llmModelNames(health: HealthResponse): string[] {
  if (health.models?.installed_llm) {
    return health.models.installed_llm
      .split("·")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (health.installed_models?.length) {
    return sortModelNames(
      health.installed_models
        .filter((m) => !m.toLowerCase().includes("embed"))
        .map((m) => m.replace(/:latest$/, ""))
    );
  }
  return [];
}

export function getInstalledModelsDisplay(health: HealthResponse): ModelsStatusDisplay | null {
  const names = llmModelNames(health);
  if (names.length > 0) {
    return { modelsText: names.join(" · ") };
  }
  if (health.models) {
    return {
      modelsText: `chat: ${health.models.chat} · eng: ${health.models.engineering}`,
    };
  }
  return null;
}

export function formatInstalledModelsLabel(health: HealthResponse): string | null {
  const display = getInstalledModelsDisplay(health);
  if (!display) return null;
  return `WSL: ${display.modelsText}`;
}
