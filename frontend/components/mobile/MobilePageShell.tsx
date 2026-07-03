"use client";

import type { ReactNode } from "react";
import ShellHeader from "@/components/ShellHeader";
import { cn } from "@/lib/utils";

interface MobilePageShellProps {
  title: string;
  subtitle?: string;
  trailing?: ReactNode;
  children: ReactNode;
  className?: string;
}

export default function MobilePageShell({
  title,
  subtitle,
  trailing,
  children,
  className,
}: MobilePageShellProps) {
  return (
    <>
      <ShellHeader className="px-4" innerClassName="gap-2" showModelsStatus={false}>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-semibold text-white">{title}</h1>
          {subtitle && <p className="truncate text-xs text-slate-500">{subtitle}</p>}
        </div>
        {trailing}
      </ShellHeader>
      <div className={cn("mobile-scroll-area flex-1 overflow-y-auto px-4 py-4", className)}>
        {children}
      </div>
    </>
  );
}
