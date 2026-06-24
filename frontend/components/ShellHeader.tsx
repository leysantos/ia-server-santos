"use client";

import ModelsStatusBadge from "@/components/ModelsStatusBadge";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface ShellHeaderProps {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
  /** Conteúdo extra à direita (ex.: modelo ativo no chat). */
  trailing?: ReactNode;
  /** Exibe rótulo WSL no canto direito — telas principais. */
  showModelsStatus?: boolean;
}

/** Cabeçalho de coluna — altura unificada via `--shell-header-h`. */
export default function ShellHeader({
  children,
  className,
  innerClassName,
  trailing,
  showModelsStatus = false,
}: ShellHeaderProps) {
  const hasTrailing = Boolean(trailing) || showModelsStatus;

  return (
    <header
      className={cn(
        "shell-header shrink-0 border-b border-white/5 bg-surface/80 backdrop-blur-xl",
        className
      )}
    >
      {hasTrailing ? (
        <div className="shell-header-split flex h-full w-full flex-col justify-center gap-2 max-lg:py-2 lg:flex-row lg:items-center lg:justify-between lg:gap-4 lg:py-0">
          <div className={cn("flex min-w-0 flex-1 items-center", innerClassName)}>{children}</div>
          <div className="flex min-w-0 max-w-full shrink-0 flex-wrap items-center justify-end gap-2 sm:gap-3">
            {trailing}
            {showModelsStatus && <ModelsStatusBadge />}
          </div>
        </div>
      ) : (
        <div className={cn("flex h-full w-full items-center", innerClassName)}>{children}</div>
      )}
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
        "shell-footer shrink-0 border-t border-white/5 bg-surface/80 backdrop-blur-xl",
        className
      )}
    >
      <div className={cn("flex h-full w-full items-center", innerClassName)}>{children}</div>
    </footer>
  );
}
