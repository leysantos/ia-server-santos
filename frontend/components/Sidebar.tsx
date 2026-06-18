"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  {
    href: "/chat",
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
    label: "Orquestrador",
    description: "Multi-disciplinar",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
  {
    href: "/history",
    label: "Histórico",
    description: "PostgreSQL",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-slate-800/80 bg-slate-950/90 backdrop-blur-xl">
      <div className="border-b border-slate-800/80 p-5">
        <Link href="/" className="group flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/20">
            <span className="text-sm font-bold text-white">IA</span>
          </div>
          <div>
            <p className="font-semibold text-white group-hover:text-cyan-300 transition-colors">
              IA Server Santos
            </p>
            <p className="text-xs text-slate-500">Engenharia SaaS</p>
          </div>
        </Link>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-3 transition-all",
                active
                  ? "bg-cyan-500/10 text-cyan-300 ring-1 ring-cyan-500/30"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              )}
            >
              <span className={active ? "text-cyan-400" : "text-slate-500"}>
                {item.icon}
              </span>
              <div>
                <p className="text-sm font-medium">{item.label}</p>
                <p className="text-xs opacity-60">{item.description}</p>
              </div>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-800/80 p-4">
        <div className="rounded-xl bg-slate-900/80 p-3 ring-1 ring-slate-800">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-xs font-medium text-slate-300">
              U
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-200">Usuário Demo</p>
              <p className="truncate text-xs text-slate-500">Auth em breve</p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
