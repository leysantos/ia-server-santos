"use client";

import MobileExportPdfButton from "@/components/mobile/MobileExportPdfButton";
import { downloadApiFile } from "@/services/api";
import { cn } from "@/lib/utils";

interface CpuExportPdfButtonProps {
  code: string;
  uf: string;
  reference: string;
  priceMode: "comd" | "semd";
  disabled?: boolean;
  className?: string;
  compact?: boolean;
}

export default function CpuExportPdfButton({
  code,
  uf,
  reference,
  priceMode,
  disabled,
  className,
  compact,
}: CpuExportPdfButtonProps) {
  const handleExport = async () => {
    const params = new URLSearchParams({
      code,
      uf,
      mode: priceMode,
    });
    if (reference) params.set("reference", reference);
    const safeCode = code.replace(/\//g, "-").slice(0, 40);
    await downloadApiFile(
      `/pricing/sync/bank/composition/export/pdf?${params.toString()}`,
      `CPU_${safeCode}_${uf}.pdf`
    );
  };

  if (compact) {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={() => void handleExport()}
        className={cn(
          "rounded-lg bg-red-600/90 px-3 py-2 text-xs font-medium text-white hover:bg-red-500 disabled:opacity-50",
          className
        )}
      >
        PDF
      </button>
    );
  }

  return (
    <MobileExportPdfButton
      disabled={disabled}
      label="Gerar PDF da CPU"
      className={className}
      onExport={handleExport}
    />
  );
}
