"use client";

import ModelsStatusBadge from "@/components/ModelsStatusBadge";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface ShellHeaderProps {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
  /** Conteúdo extra à direita (ex.: modelo ativo no chat, status Gemini). */
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
        <div className="shell-header-split">
          <div className={cn("shell-header-main", innerClassName)}>{children}</div>
          <div className="shell-header-trailing">
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
