"use client";

import { cn } from "@/lib/utils";

export type PipelineStepStatus = "pending" | "running" | "done" | "error";

export interface PipelineStep {
  id: string;
  label: string;
  status: PipelineStepStatus;
  detail?: string;
}

interface PipelineStepsProps {
  steps: PipelineStep[];
  className?: string;
}

const STATUS_STYLES: Record<PipelineStepStatus, string> = {
  pending: "bg-slate-800 text-slate-500 ring-slate-700",
  running: "bg-cyan-500/20 text-cyan-300 ring-cyan-500/40 animate-pulse",
  done: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  error: "bg-red-500/15 text-red-300 ring-red-500/40",
};

export default function PipelineSteps({ steps, className }: PipelineStepsProps) {
  if (!steps.length) return null;

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {steps.map((step, index) => (
        <div key={step.id} className="flex items-center gap-2">
          <div
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium ring-1",
              STATUS_STYLES[step.status]
            )}
            title={step.detail}
          >
            {step.label}
          </div>
          {index < steps.length - 1 && (
            <span className="text-slate-600" aria-hidden>
              →
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
