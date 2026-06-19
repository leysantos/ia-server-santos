"use client";

interface ActionDialogProps {
  open: boolean;
  title: string;
  message: string;
  variant?: "success" | "error" | "confirm" | "info";
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void;
  onCancel: () => void;
}

export default function ActionDialog({
  open,
  title,
  message,
  variant = "info",
  confirmLabel = "OK",
  cancelLabel = "Cancelar",
  onConfirm,
  onCancel,
}: ActionDialogProps) {
  if (!open) return null;

  const colors = {
    success: "ring-emerald-500/40 bg-emerald-500/10",
    error: "ring-red-500/40 bg-red-500/10",
    confirm: "ring-amber-500/40 bg-slate-900",
    info: "ring-cyan-500/40 bg-slate-900",
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div className={`w-full max-w-md rounded-xl p-6 ring-1 ${colors[variant]}`}>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="mt-2 text-sm text-slate-300 whitespace-pre-wrap">{message}</p>
        <div className="mt-5 flex justify-end gap-2">
          {variant === "confirm" && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white"
            >
              {cancelLabel}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              onConfirm?.();
              if (variant !== "confirm") onCancel();
            }}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${
              variant === "error"
                ? "bg-red-600/30 text-red-200 hover:bg-red-600/40"
                : variant === "success"
                  ? "bg-emerald-600/30 text-emerald-200 hover:bg-emerald-600/40"
                  : "bg-cyan-600/30 text-cyan-200 hover:bg-cyan-600/40"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
