"use client";

import { Suspense, useCallback, useState } from "react";
import Link from "next/link";
import ActionDialog from "@/components/ActionDialog";
import BudgetOrcaFacilWorkspace from "@/components/BudgetOrcaFacilWorkspace";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";

type DialogState = {
  open: boolean;
  title: string;
  message: string;
  variant: "success" | "error" | "confirm" | "info";
  onConfirm?: () => void;
};

function OrcaFacilContent() {
  const [dialog, setDialog] = useState<DialogState>({
    open: false,
    title: "",
    message: "",
    variant: "info",
  });

  const showSuccess = useCallback((message: string, title = "OrçaFacil") => {
    setDialog({ open: true, title, message, variant: "success" });
  }, []);

  const showError = useCallback((err: unknown, title = "OrçaFacil") => {
    const message = err instanceof Error ? err.message : String(err);
    setDialog({ open: true, title, message, variant: "error" });
  }, []);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ShellHeader>
        <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-slate-500">
              <Link href="/budget" className="hover:text-slate-300">
                Orçamento
              </Link>
              <span className="mx-1">/</span>
              <span className="text-slate-300">OrçaFacil</span>
            </p>
            <h1 className="truncate text-lg font-semibold text-white">OrçaFacil</h1>
          </div>
        </div>
      </ShellHeader>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-3 md:p-4">
        <BudgetOrcaFacilWorkspace onError={showError} onSuccess={showSuccess} />
      </div>

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        variant={dialog.variant}
        onCancel={() => setDialog((d) => ({ ...d, open: false, onConfirm: undefined }))}
        onConfirm={
          dialog.onConfirm
            ? () => {
                dialog.onConfirm?.();
                setDialog((d) => ({ ...d, open: false, onConfirm: undefined }));
              }
            : undefined
        }
      />
    </div>
  );
}

export default function OrcaFacilPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center">
          <LoadingSpinner />
        </div>
      }
    >
      <OrcaFacilContent />
    </Suspense>
  );
}
