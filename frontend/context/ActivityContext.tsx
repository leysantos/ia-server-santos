"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ActivitySource =
  | "chat"
  | "orchestrator"
  | "vision"
  | "budget"
  | "upload"
  | "review"
  | "system";

export type ActivityStatus = "running" | "done" | "error";

export interface LiveActivityEntry {
  id: string;
  source: ActivitySource;
  message: string;
  status: ActivityStatus;
  phase?: string;
  agent?: string;
  discipline?: string;
  projectId?: string;
  timestamp: number;
}

interface ActivityContextValue {
  entries: LiveActivityEntry[];
  open: boolean;
  setOpen: (open: boolean) => void;
  pushActivity: (entry: Omit<LiveActivityEntry, "id" | "timestamp"> & { id?: string }) => void;
  updateActivity: (id: string, patch: Partial<LiveActivityEntry>) => void;
  clearActivity: () => void;
}

const ActivityContext = createContext<ActivityContextValue | null>(null);

let counter = 0;

function nextId() {
  counter += 1;
  return `act-${Date.now()}-${counter}`;
}

export function ActivityProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<LiveActivityEntry[]>([]);
  const [open, setOpen] = useState(false);

  const pushActivity = useCallback(
    (entry: Omit<LiveActivityEntry, "id" | "timestamp"> & { id?: string }) => {
      const row: LiveActivityEntry = {
        id: entry.id ?? nextId(),
        timestamp: Date.now(),
        source: entry.source,
        message: entry.message,
        status: entry.status,
        phase: entry.phase,
        agent: entry.agent,
        discipline: entry.discipline,
        projectId: entry.projectId,
      };
      setEntries((prev) => [row, ...prev].slice(0, 80));
      setOpen(true);
    },
    []
  );

  const updateActivity = useCallback((id: string, patch: Partial<LiveActivityEntry>) => {
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  }, []);

  const clearActivity = useCallback(() => setEntries([]), []);

  const value = useMemo(
    () => ({ entries, open, setOpen, pushActivity, updateActivity, clearActivity }),
    [entries, open, pushActivity, updateActivity, clearActivity]
  );

  return <ActivityContext.Provider value={value}>{children}</ActivityContext.Provider>;
}

export function useActivity() {
  const ctx = useContext(ActivityContext);
  if (!ctx) {
    throw new Error("useActivity must be used within ActivityProvider");
  }
  return ctx;
}

export function useActivityOptional() {
  return useContext(ActivityContext);
}
