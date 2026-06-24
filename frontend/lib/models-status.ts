import type { HealthResponse } from "@/types/api";

export interface ModelsStatusDisplay {
  /** Texto após o prefixo WSL (modelos separados por ·). */
  modelsText: string;
}

function llmModelNames(health: HealthResponse): string[] {
  if (health.models?.installed_llm) {
    return health.models.installed_llm
      .split("·")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (health.installed_models?.length) {
    return health.installed_models
      .filter((m) => !m.toLowerCase().includes("embed"))
      .map((m) => m.replace(/:latest$/, ""));
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
