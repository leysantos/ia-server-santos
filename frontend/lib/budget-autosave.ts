/** Intervalo para reidratar sessão in-memory no backend (mitiga R-23). */
export const BUDGET_SESSION_HEARTBEAT_MS = 60_000;

/** Intervalo para persistir orçamento salvo no banco sem diálogo. */
export const BUDGET_DB_AUTOSAVE_MS = 180_000;

export function formatAutoSaveHint(lastSavedAt: Date | null, saving: boolean): string | null {
  if (saving) return "Salvando automaticamente…";
  if (!lastSavedAt) return "Rascunho em sessão local";
  const diffSec = Math.floor((Date.now() - lastSavedAt.getTime()) / 1000);
  if (diffSec < 15) return "Salvo automaticamente agora";
  if (diffSec < 60) return `Salvo automaticamente há ${diffSec}s`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `Salvo automaticamente há ${diffMin} min`;
  return `Salvo automaticamente às ${lastSavedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}
