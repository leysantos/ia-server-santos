"use client";

interface LoadingSpinnerProps {
  label?: string;
  size?: "sm" | "md" | "lg";
}

const sizeMap = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-10 w-10 border-[3px]",
};

export default function LoadingSpinner({
  label = "Processando...",
  size = "md",
}: LoadingSpinnerProps) {
  return (
    <div className="flex items-center gap-3 text-slate-400">
      <div
        className={`${sizeMap[size]} animate-spin rounded-full border-slate-600 border-t-cyan-400`}
      />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
