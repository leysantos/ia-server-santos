import type { HealthResponse } from "@/types/api";

export function formatInstalledModelsLabel(health: HealthResponse): string | null {
  if (health.models?.installed_llm) {
    return `WSL: ${health.models.installed_llm}`;
  }
  if (health.installed_models?.length) {
    const llms = health.installed_models.filter((m) => !m.toLowerCase().includes("embed"));
    if (llms.length === 0) return null;
    return `WSL: ${llms.map((m) => m.replace(/:latest$/, "")).join(" · ")}`;
  }
  if (health.models) {
    return `chat: ${health.models.chat} · eng: ${health.models.engineering}`;
  }
  return null;
}
