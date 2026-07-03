import type { BudgetSessionResponse } from "@/types/api";
import { request } from "./http";

export const BUDGET_SESSION_RESTORED = "budget-session-restored";
const BUDGET_SESSION_STORAGE_KEY = "iaserver.budget.session";

let budgetSessionSnapshot: BudgetSessionResponse | null = null;

function persistBudgetSessionStorage(session: BudgetSessionResponse | null): void {
  if (typeof window === "undefined") return;
  try {
    if (!session) {
      sessionStorage.removeItem(BUDGET_SESSION_STORAGE_KEY);
      return;
    }
    sessionStorage.setItem(BUDGET_SESSION_STORAGE_KEY, JSON.stringify(session));
  } catch {
    /* quota / private mode */
  }
}

export function isSessionNotFoundError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return msg.includes("Sessão não encontrada") || msg.includes("Sessao nao encontrada");
}

export async function restoreBudgetSessionFromStorage(): Promise<BudgetSessionResponse | null> {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(BUDGET_SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    const payload = JSON.parse(raw) as BudgetSessionResponse;
    if (!payload?.rows?.length && !payload?.items?.length) return null;
    const restored = await request<BudgetSessionResponse>("/pricing/budget/restore", {
      method: "POST",
      body: JSON.stringify({ payload }),
    });
    budgetSessionSnapshot = restored;
    persistBudgetSessionStorage(restored);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(BUDGET_SESSION_RESTORED, { detail: restored }));
    }
    return restored;
  } catch {
    return null;
  }
}

export function syncBudgetSessionSnapshot(session: BudgetSessionResponse | null): void {
  budgetSessionSnapshot = session;
  persistBudgetSessionStorage(session);
}

export function clearBudgetSessionSnapshot(): void {
  budgetSessionSnapshot = null;
  persistBudgetSessionStorage(null);
}

async function restoreBudgetSessionSnapshot(): Promise<BudgetSessionResponse> {
  if (!budgetSessionSnapshot?.session_id) {
    throw new Error("Sessão não encontrada");
  }
  const restored = await request<BudgetSessionResponse>("/pricing/budget/restore", {
    method: "POST",
    body: JSON.stringify({ payload: budgetSessionSnapshot }),
  });
  budgetSessionSnapshot = restored;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(BUDGET_SESSION_RESTORED, { detail: restored }));
  }
  return restored;
}

export async function withBudgetSessionRecovery<T>(
  sessionId: string,
  fn: (sid: string) => Promise<T>
): Promise<T> {
  try {
    return await fn(sessionId);
  } catch (err) {
    if (!isSessionNotFoundError(err) || !budgetSessionSnapshot) throw err;
    const restored = await restoreBudgetSessionSnapshot();
    return fn(restored.session_id);
  }
}
