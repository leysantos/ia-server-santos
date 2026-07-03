"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, syncBudgetSessionSnapshot } from "@/services/api";
import {
  BUDGET_DB_AUTOSAVE_MS,
  BUDGET_SESSION_HEARTBEAT_MS,
  formatAutoSaveHint,
} from "@/lib/budget-autosave";
import type { BudgetSessionResponse } from "@/types/api";

type PersistBudgetFn = (opts?: {
  showDialog?: boolean;
  silent?: boolean;
}) => Promise<BudgetSessionResponse | undefined>;

interface UseBudgetAutoSaveOptions {
  session: BudgetSessionResponse | null;
  activeDbId: string | null;
  baselineFrozen?: boolean;
  loading: boolean;
  persistBudget: PersistBudgetFn;
  enabled?: boolean;
}

export function useBudgetAutoSave({
  session,
  activeDbId,
  baselineFrozen,
  loading,
  persistBudget,
  enabled = true,
}: UseBudgetAutoSaveOptions) {
  const [lastAutoSavedAt, setLastAutoSavedAt] = useState<Date | null>(null);
  const [autoSaving, setAutoSaving] = useState(false);
  const dirtyRef = useRef(false);
  const heartbeatBusyRef = useRef(false);
  const dbSaveBusyRef = useRef(false);
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const persistRef = useRef(persistBudget);
  persistRef.current = persistBudget;

  useEffect(() => {
    if (!session) {
      dirtyRef.current = false;
      return;
    }
    dirtyRef.current = true;
  }, [session]);

  const runSessionHeartbeat = useCallback(async () => {
    const current = sessionRef.current;
    if (!current || heartbeatBusyRef.current) return;
    heartbeatBusyRef.current = true;
    try {
      syncBudgetSessionSnapshot(current);
      const restored = await api.pricingRestoreSession(current);
      sessionRef.current = restored;
      syncBudgetSessionSnapshot(restored);
    } catch {
      /* offline / API indisponível — snapshot local permanece */
    } finally {
      heartbeatBusyRef.current = false;
    }
  }, []);

  const runDbAutoSave = useCallback(async () => {
    const current = sessionRef.current;
    if (!current || !activeDbId || baselineFrozen || loading || dbSaveBusyRef.current) return;
    if (!dirtyRef.current) return;

    dbSaveBusyRef.current = true;
    setAutoSaving(true);
    try {
      const saved = await persistRef.current({ showDialog: false, silent: true });
      if (saved) {
        dirtyRef.current = false;
        setLastAutoSavedAt(new Date());
        sessionRef.current = saved;
      }
    } catch {
      /* conflito de versão / rede — usuário salva manualmente */
    } finally {
      dbSaveBusyRef.current = false;
      setAutoSaving(false);
    }
  }, [activeDbId, baselineFrozen, loading]);

  useEffect(() => {
    if (!enabled || !session) return;

    void runSessionHeartbeat();
    const heartbeatTimer = window.setInterval(() => {
      void runSessionHeartbeat();
    }, BUDGET_SESSION_HEARTBEAT_MS);

    const dbTimer = window.setInterval(() => {
      void runDbAutoSave();
    }, BUDGET_DB_AUTOSAVE_MS);

    return () => {
      window.clearInterval(heartbeatTimer);
      window.clearInterval(dbTimer);
    };
  }, [enabled, session?.session_id, activeDbId, runDbAutoSave, runSessionHeartbeat]);

  useEffect(() => {
    if (!session) return;
    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        syncBudgetSessionSnapshot(sessionRef.current);
      }
    };
    const onBeforeUnload = () => {
      syncBudgetSessionSnapshot(sessionRef.current);
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [session?.session_id]);

  const autoSaveHint = session
    ? formatAutoSaveHint(activeDbId ? lastAutoSavedAt : null, autoSaving)
    : null;

  return { autoSaveHint, lastAutoSavedAt, autoSaving };
}
