"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface ShellHeaderProps {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
}

/** Cabeçalho de coluna — altura unificada via `--shell-header-h`. */
export default function ShellHeader({ children, className, innerClassName }: ShellHeaderProps) {
  return (
    <header
      className={cn(
        "shell-header shrink-0 border-b border-slate-800/80 bg-slate-950/50 backdrop-blur-xl",
        className
      )}
    >
      <div className={cn("flex h-full w-full items-center", innerClassName)}>{children}</div>
    </header>
  );
}

interface ShellFooterProps {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
}

/** Rodapé de coluna — altura unificada via `--shell-footer-h` + `--shell-safe-bottom`. */
export function ShellFooter({ children, className, innerClassName }: ShellFooterProps) {
  return (
    <footer
      className={cn(
        "shell-footer shrink-0 border-t border-slate-800/80 bg-slate-950/50 backdrop-blur-xl",
        className
      )}
    >
      <div className={cn("flex h-full w-full items-center", innerClassName)}>{children}</div>
    </footer>
  );
}
