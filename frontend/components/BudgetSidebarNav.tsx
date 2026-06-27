"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

const BUDGET_ICON = (
  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.5}
      d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
    />
  </svg>
);

const SUB_ACTIONS = [
  { id: "new", label: "Novo orçamento", href: "/budget?action=new" },
  { id: "models", label: "Cadastrar modelo de orçamento", href: "/budget/models" },
  { id: "open", label: "Abrir módulo de orçamento", href: "/budget" },
] as const;

export default function BudgetSidebarNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { canAccessModule } = useAuth();
  const budgetAccess = canAccessModule("budget");
  const [expanded, setExpanded] = useState(false);

  const budgetActive =
    pathname === "/budget" ||
    pathname.startsWith("/budget/") ||
    pathname.startsWith("/budget?");

  useEffect(() => {
    if (budgetActive) setExpanded(true);
  }, [budgetActive]);

  const handleSubAction = useCallback(
    (_action: (typeof SUB_ACTIONS)[number]["id"], href: string) => {
      router.push(href);
    },
    [router]
  );

  if (!budgetAccess.visible) return null;

  return (
    <div className="space-y-1">
      <div
        className={cn(
          "flex items-stretch gap-0.5 rounded-xl transition-all",
          budgetActive && !budgetAccess.blocked && "bg-brand-500/10 ring-1 ring-brand-500/30"
        )}
      >
        <Link
          href={budgetAccess.blocked ? "#" : "/budget"}
          onClick={(e) => {
            if (budgetAccess.blocked) e.preventDefault();
          }}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-3 rounded-xl px-3 py-3 transition-all",
            budgetAccess.blocked
              ? "cursor-not-allowed text-slate-600 opacity-60"
              : budgetActive
                ? "text-brand-300"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
          )}
          title={budgetAccess.blocked ? "Módulo visível, acesso bloqueado" : undefined}
        >
          <span className={budgetActive && !budgetAccess.blocked ? "text-brand-400" : "text-slate-500"}>
            {BUDGET_ICON}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium">Orçamento</p>
            <p className="text-xs opacity-60">
              {budgetAccess.blocked ? "Acesso bloqueado" : "Pricing Engine"}
            </p>
          </div>
        </Link>
        <button
          type="button"
          disabled={budgetAccess.blocked}
          onClick={() => setExpanded((v) => !v)}
          className={cn(
            "flex w-9 shrink-0 items-center justify-center rounded-xl transition-colors",
            budgetActive
              ? "text-brand-400 hover:bg-brand-500/15"
              : "text-slate-500 hover:bg-white/5 hover:text-slate-300"
          )}
          aria-expanded={expanded}
          aria-label={expanded ? "Recolher menu de orçamento" : "Expandir menu de orçamento"}
        >
          <svg
            className={cn("h-4 w-4 transition-transform", expanded && "rotate-180")}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {expanded && !budgetAccess.blocked && (
        <div className="ml-3 space-y-0.5 border-l border-white/10 py-1 pl-3">
          {SUB_ACTIONS.map((action) => (
            <button
              key={action.id}
              type="button"
              onClick={() => handleSubAction(action.id, action.href)}
              className={cn(
                "block w-full rounded-lg px-2.5 py-2 text-left text-xs transition-colors",
                action.id === "models" && pathname === "/budget/models"
                  ? "bg-brand-500/15 text-brand-200"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              )}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
