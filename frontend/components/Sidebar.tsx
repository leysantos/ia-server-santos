"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ShellHeader, { ShellFooter } from "@/components/ShellHeader";
import BudgetSidebarNav from "@/components/BudgetSidebarNav";
import SystemBenchmarkPanel from "@/components/SystemBenchmarkPanel";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

const navItems = [
  {
    href: "/chat",
    moduleId: "chat",
    label: "Chat IA",
    description: "Single-domain",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
      </svg>
    ),
  },
  {
    href: "/orchestrate",
    moduleId: "orchestrate",
    label: "Orquestrador",
    description: "Multi-disciplinar",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
  {
    href: "/copilot",
    moduleId: "copilot",
    label: "Copilot",
    description: "Planejamento IA",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
  },
  {
    href: "/aed",
    moduleId: "aed",
    label: "AED",
    description: "Design autônomo",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
      </svg>
    ),
  },
  {
    href: "/projects",
    moduleId: "projects",
    label: "Projetos",
    description: "Workspace",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
    ),
  },
  {
    href: "/console",
    moduleId: "console",
    label: "Console",
    description: "Ops · GPU · Live",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    href: "/history",
    moduleId: "history",
    label: "Histórico",
    description: "PostgreSQL",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    href: "/settings",
    moduleId: "settings",
    label: "Configurações",
    description: "Base de conhecimento",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, authEnabled, logout, canAccessModule } = useAuth();
  const initials = (user?.full_name || user?.username || "U").slice(0, 1).toUpperCase();

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-white/5 bg-surface/90 backdrop-blur-xl md:w-64">
      <ShellHeader>
        <Link href="/" className="group flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 shadow-brand-sm ring-1 ring-brand-400/20">
            <span className="text-sm font-bold text-white">IA</span>
          </div>
          <div className="min-w-0">
            <p className="truncate font-semibold text-white transition-colors group-hover:text-brand-300">
              IA Server Santos
            </p>
            <p className="truncate text-xs text-slate-500">Engenharia SaaS</p>
          </div>
        </Link>
      </ShellHeader>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        <BudgetSidebarNav />
        {navItems.map((item) => {
          const access = canAccessModule(item.moduleId);
          if (!access.visible) return null;
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const className = cn(
            "flex items-center gap-3 rounded-xl px-3 py-3 transition-all",
            access.blocked
              ? "cursor-not-allowed text-slate-600 opacity-60"
              : active
                ? "bg-brand-500/10 text-brand-300 ring-1 ring-brand-500/30"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
          );
          const inner = (
            <>
              <span className={active && !access.blocked ? "text-brand-400" : "text-slate-500"}>
                {item.icon}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium">{item.label}</p>
                <p className="text-xs opacity-60">
                  {access.blocked ? "Acesso bloqueado" : item.description}
                </p>
              </div>
            </>
          );
          if (access.blocked) {
            return (
              <div key={item.href} className={className} title="Módulo visível, acesso bloqueado">
                {inner}
              </div>
            );
          }
          return (
            <Link key={item.href} href={item.href} className={className}>
              {inner}
            </Link>
          );
        })}
      </nav>

      <div className="shrink-0 border-t border-white/5 bg-surface/95 px-5 py-3">
        <SystemBenchmarkPanel />
      </div>

      <ShellFooter innerClassName="items-stretch">
        <div className="app-card w-full p-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-elevated text-xs font-medium text-slate-300 ring-1 ring-white/10">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-200">
                {user?.full_name || user?.username || "Convidado"}
              </p>
              <p className="truncate text-xs text-slate-500">
                {authEnabled ? user?.role_label || user?.role || "—" : "Auth desabilitada"}
              </p>
            </div>
            {authEnabled && user ? (
              <button
                type="button"
                onClick={logout}
                className="shrink-0 text-xs text-slate-500 hover:text-slate-300"
                title="Sair"
              >
                Sair
              </button>
            ) : null}
          </div>
        </div>
      </ShellFooter>
    </aside>
  );
}
