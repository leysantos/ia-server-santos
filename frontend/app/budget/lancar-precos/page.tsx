"use client";

import { Suspense, useCallback, useState } from "react";
import Link from "next/link";
import ActionDialog from "@/components/ActionDialog";
import BudgetLancarPrecosWorkspace from "@/components/BudgetLancarPrecosWorkspace";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";

type DialogState = {
  open: boolean;
  title: string;
  message: string;
  variant: "success" | "error" | "confirm" | "info";
  onConfirm?: () => void;
};

function LancarPrecosContent() {
  const [dialog, setDialog] = useState<DialogState>({
    open: false,
    title: "",
    message: "",
    variant: "info",
  });

  const showSuccess = useCallback((message: string, title = "Lançar Preços") => {
    setDialog({ open: true, title, message, variant: "success" });
  }, []);

  const showError = useCallback((err: unknown, title = "Lançar Preços") => {
    const message = err instanceof Error ? err.message : String(err);
    setDialog({ open: true, title, message, variant: "error" });
  }, []);

  const requestDelete = useCallback((onConfirm: () => void) => {
    setDialog({
      open: true,
      title: "Excluir orçamento",
      message: "Remover o job de lançamento de preços e o orçamento vinculado no banco? Esta ação não pode ser desfeita.",
      variant: "confirm",
      onConfirm,
    });
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
              <span className="text-slate-300">Lançar Preços</span>
            </p>
            <h1 className="truncate text-lg font-semibold text-white">Lançar Preços</h1>
          </div>
        </div>
      </ShellHeader>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-4">
        <BudgetLancarPrecosWorkspace
          onError={showError}
          onSuccess={showSuccess}
          onConfirmDelete={requestDelete}
        />
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

export default function LancarPrecosPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center">
          <LoadingSpinner label="Carregando…" />
        </div>
      }
    >
      <LancarPrecosContent />
    </Suspense>
  );
}
