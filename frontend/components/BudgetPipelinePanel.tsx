"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

export interface PricingCandidate {
  code: string;
  description: string;
  unit?: string;
  price?: number;
  score?: number;
  source?: string;
}

export interface PricingResolveEvent {
  line_name?: string;
  line_code?: string;
  query?: string;
  unit?: string;
  resolved?: boolean;
  method?: string;
  score?: number;
  faiss_available?: boolean;
  selected_code?: string | null;
  selected_description?: string | null;
  selected_price?: number | null;
  candidates?: PricingCandidate[];
  llm_model?: string | null;
}

export interface PipelineLogEntry {
  id: string;
  type: "status" | "token" | "step" | "error" | "done" | "pricing_resolve";
  message: string;
  step?: string;
  llmModel?: string;
  timestamp: number;
  pricing?: PricingResolveEvent;
  faissIndex?: { indexed?: number; label?: string; total_rows?: number };
}

interface BudgetPipelinePanelProps {
  logs: PipelineLogEntry[];
  streaming: boolean;
  llmTokens?: string;
}

function methodLabel(method?: string): string {
  switch (method) {
    case "llm":
      return "LLM";
    case "model_wbs":
      return "modelo WBS";
    case "code":
      return "código";
    case "faiss":
      return "FAISS";
    case "faiss+llm":
      return "FAISS+LLM";
    case "fuzzy":
      return "fuzzy";
    case "fuzzy+llm":
      return "fuzzy+LLM";
    case "unresolved":
      return "sem match";
    default:
      return method ?? "—";
  }
}

export default function BudgetPipelinePanel({
  logs,
  streaming,
  llmTokens = "",
}: BudgetPipelinePanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, llmTokens]);

  return (
    <section className="rounded-xl bg-slate-950/80 ring-1 ring-violet-500/30">
      <div className="flex items-center justify-between border-b border-slate-800/80 px-4 py-2.5">
        <h3 className="text-xs font-medium uppercase tracking-wider text-violet-300">
          Pipeline IA — tempo real
        </h3>
        {streaming && (
          <span className="flex items-center gap-1.5 text-xs text-cyan-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
            Executando…
          </span>
        )}
      </div>
      <div className="max-h-72 overflow-y-auto p-3 font-mono text-xs">
        {logs.length === 0 && !streaming && (
          <p className="text-slate-500">Aguardando prompt — o pipeline aparecerá aqui.</p>
        )}
        {logs.map((log) => (
          <div
            key={log.id}
            className={cn(
              "mb-1 rounded px-2 py-1",
              log.type === "error" && "bg-red-500/10 text-red-300",
              log.type === "status" && "text-slate-400",
              log.type === "step" && "text-cyan-400/90",
              log.type === "done" && "text-emerald-400",
              log.type === "pricing_resolve" && "bg-slate-900/50 text-amber-200/90"
            )}
          >
            <span className="text-slate-600">
              {new Date(log.timestamp).toLocaleTimeString("pt-BR")}
            </span>{" "}
            {log.step && <span className="text-violet-400">[{log.step}] </span>}
            {log.type === "pricing_resolve" && log.pricing ? (
              <div className="mt-0.5">
                <span className={log.pricing.resolved ? "text-emerald-400" : "text-red-400"}>
                  {log.pricing.resolved ? "✓" : "✗"}
                </span>{" "}
                <span className="text-slate-200">{log.pricing.line_name ?? log.pricing.query}</span>
                {" → "}
                <span className="text-cyan-300">
                  {log.pricing.selected_code ?? "—"}
                </span>
                <span className="text-slate-500">
                  {" "}
                  · {methodLabel(log.pricing.method)} · score {(log.pricing.score ?? 0).toFixed(2)}
                </span>
                {log.pricing.candidates && log.pricing.candidates.length > 0 && (
                  <div className="mt-1 pl-3 text-[10px] text-slate-500">
                    top:{" "}
                    {log.pricing.candidates
                      .slice(0, 3)
                      .map((c) => `${c.code} (${(c.score ?? 0).toFixed(2)})`)
                      .join(" · ")}
                  </div>
                )}
              </div>
            ) : (
              <>
                {log.message}
                {log.llmModel && <span className="text-slate-500"> · {log.llmModel}</span>}
                {log.faissIndex && (
                  <span className="text-slate-500">
                    {" "}
                    · FAISS {log.faissIndex.indexed?.toLocaleString("pt-BR") ?? 0} composições
                    {log.faissIndex.label ? ` (${log.faissIndex.label})` : ""}
                  </span>
                )}
              </>
            )}
          </div>
        ))}
        {llmTokens && (
          <div className="mt-2 rounded bg-slate-900/60 p-2 text-slate-300 whitespace-pre-wrap break-words">
            <span className="text-violet-400">[wbs_planner] </span>
            {llmTokens}
            <span className="animate-pulse text-violet-400">▌</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </section>
  );
}
