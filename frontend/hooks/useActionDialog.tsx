"use client";

import { useCallback, useRef, useState } from "react";
import ActionDialog from "@/components/ActionDialog";

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

export interface AlertOptions {
  title: string;
  message: string;
  variant?: "success" | "error" | "info";
  confirmLabel?: string;
}

type DialogConfig = {
  open: boolean;
  title: string;
  message: string;
  variant: "success" | "error" | "confirm" | "info";
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
};

const CLOSED: DialogConfig = {
  open: false,
  title: "",
  message: "",
  variant: "info",
};

export function useActionDialog() {
  const [dialog, setDialog] = useState<DialogConfig>(CLOSED);
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  const close = useCallback(() => {
    resolverRef.current?.(false);
    resolverRef.current = null;
    setDialog(CLOSED);
  }, []);

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      setDialog({
        open: true,
        title: options.title,
        message: options.message,
        variant: "confirm",
        confirmLabel: options.confirmLabel ?? "Confirmar",
        cancelLabel: options.cancelLabel ?? "Cancelar",
        destructive: options.destructive ?? false,
      });
    });
  }, []);

  const alert = useCallback((options: AlertOptions): Promise<void> => {
    return new Promise((resolve) => {
      resolverRef.current = () => resolve();
      setDialog({
        open: true,
        title: options.title,
        message: options.message,
        variant: options.variant ?? "info",
        confirmLabel: options.confirmLabel ?? "OK",
      });
    });
  }, []);

  const handleConfirm = useCallback(() => {
    resolverRef.current?.(true);
    resolverRef.current = null;
    setDialog(CLOSED);
  }, []);

  const ActionDialogHost = useCallback(
    () => (
      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        variant={dialog.variant}
        confirmLabel={dialog.confirmLabel}
        cancelLabel={dialog.cancelLabel}
        destructive={dialog.destructive}
        onConfirm={handleConfirm}
        onCancel={close}
      />
    ),
    [dialog, handleConfirm, close]
  );

  return { confirm, alert, ActionDialogHost, close };
}
