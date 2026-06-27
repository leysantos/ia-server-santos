"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

interface ActionDialogProps {
  open: boolean;
  title: string;
  message: string;
  variant?: "success" | "error" | "confirm" | "info";
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm?: () => void;
  onCancel: () => void;
}

const VARIANT_STYLES = {
  success: {
    ring: "ring-emerald-500/30",
    icon: "text-emerald-400",
    confirm: "bg-emerald-600/30 text-emerald-200 hover:bg-emerald-600/40",
  },
  error: {
    ring: "ring-red-500/30",
    icon: "text-red-400",
    confirm: "bg-red-600/30 text-red-200 hover:bg-red-600/40",
  },
  confirm: {
    ring: "ring-slate-700/80",
    icon: "text-amber-400",
    confirm: "bg-cyan-600/30 text-cyan-200 hover:bg-cyan-600/40",
  },
  info: {
    ring: "ring-cyan-500/30",
    icon: "text-cyan-400",
    confirm: "bg-cyan-600/30 text-cyan-200 hover:bg-cyan-600/40",
  },
};

function DialogIcon({ variant, destructive }: { variant: ActionDialogProps["variant"]; destructive?: boolean }) {
  if (destructive) {
    return (
      <svg className="h-6 w-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
        />
      </svg>
    );
  }

  const styles = VARIANT_STYLES[variant ?? "info"];

  if (variant === "success") {
    return (
      <svg className={cn("h-6 w-6", styles.icon)} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 13l4 4L19 7" />
      </svg>
    );
  }

  if (variant === "error") {
    return (
      <svg className={cn("h-6 w-6", styles.icon)} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
      </svg>
    );
  }

  return (
    <svg className={cn("h-6 w-6", styles.icon)} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

export default function ActionDialog({
  open,
  title,
  message,
  variant = "info",
  confirmLabel = "OK",
  cancelLabel = "Cancelar",
  destructive = false,
  onConfirm,
  onCancel,
}: ActionDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const [mounted, setMounted] = useState(false);
  const styles = VARIANT_STYLES[variant];

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;

    confirmRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };

    document.addEventListener("keydown", onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onCancel]);

  if (!open || !mounted) return null;

  const isConfirm = variant === "confirm";

  const confirmButtonClass = destructive
    ? "bg-red-600 text-white hover:bg-red-500"
    : variant === "error"
      ? styles.confirm
      : styles.confirm;

  const handlePrimaryClick = () => {
    if (isConfirm && onConfirm) {
      void Promise.resolve(onConfirm()).then(() => onCancel());
      return;
    }
    onCancel();
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
      role="presentation"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="action-dialog-title"
        aria-describedby="action-dialog-message"
        className={cn(
          "w-full max-w-md rounded-2xl bg-slate-900 p-6 shadow-2xl ring-1 transition-all duration-200",
          styles.ring
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-800/80">
            <DialogIcon variant={variant} destructive={destructive} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 id="action-dialog-title" className="text-lg font-semibold text-white">
              {title}
            </h3>
            <p id="action-dialog-message" className="mt-2 text-sm leading-relaxed text-slate-300 whitespace-pre-wrap">
              {message}
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          {variant === "confirm" && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg px-4 py-2 text-sm text-slate-400 transition hover:bg-slate-800 hover:text-white"
            >
              {cancelLabel}
            </button>
          )}
          <button
            ref={confirmRef}
            type="button"
            disabled={isConfirm && !onConfirm}
            onClick={handlePrimaryClick}
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
              confirmButtonClass
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
