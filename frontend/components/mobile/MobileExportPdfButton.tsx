"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface MobileExportPdfButtonProps {
  onExport: () => Promise<void>;
  disabled?: boolean;
  label?: string;
  className?: string;
}

export default function MobileExportPdfButton({
  onExport,
  disabled,
  label = "Gerar PDF",
  className,
}: MobileExportPdfButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      await onExport();
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      disabled={disabled || loading}
      onClick={() => void handleClick()}
      className={cn(
        "inline-flex items-center gap-2 rounded-xl bg-red-600/90 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-red-500 disabled:opacity-50",
        className
      )}
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      {loading ? "Gerando…" : label}
    </button>
  );
}
