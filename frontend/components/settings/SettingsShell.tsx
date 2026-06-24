"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import { SETTINGS_MODULES, resolveSettingsModule } from "@/components/settings/settings-nav";
import { useSettingsKnowledgeOptional } from "@/contexts/SettingsKnowledgeContext";
import { cn } from "@/lib/utils";

function SettingsNav({
  onNavigate,
  className,
}: {
  onNavigate?: () => void;
  className?: string;
}) {
  const pathname = usePathname();

  return (
    <nav className={cn("flex flex-col gap-1 p-3", className)}>
      <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
        Módulos
      </p>
      {SETTINGS_MODULES.map((item) => {
        const active =
          item.href === "/settings"
            ? pathname === "/settings"
            : pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.id}
            href={item.href}
            onClick={onNavigate}
            className={cn(
              "flex items-start gap-3 rounded-xl px-3 py-2.5 text-left transition",
              active
                ? "bg-brand-500/15 text-brand-100 ring-1 ring-brand-500/30"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
            )}
          >
            <span className={cn("mt-0.5", active ? "text-cyan-400" : "text-slate-500")}>
              {item.icon}
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-medium leading-tight">{item.label}</span>
              <span className="mt-0.5 block text-xs leading-snug text-slate-500">{item.description}</span>
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

export default function SettingsShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const settingsModule = resolveSettingsModule(pathname);
  const knowledge = useSettingsKnowledgeOptional();
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const loading = knowledge?.loading ?? false;

  return (
    <>
      <ShellHeader className="px-4 sm:px-6" showModelsStatus>
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <button
            type="button"
            aria-label="Abrir menu de configurações"
            onClick={() => setDrawerOpen(true)}
            className="rounded-lg p-2 text-slate-400 ring-1 ring-slate-700 hover:bg-slate-800 hover:text-white lg:hidden"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="min-w-0">
            <p className="text-xs text-slate-500">Configurações</p>
            <h1 className="truncate text-lg font-semibold text-white">{settingsModule.label}</h1>
          </div>
        </div>
      </ShellHeader>

      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {/* Cortina mobile */}
        {drawerOpen && (
          <button
            type="button"
            aria-label="Fechar menu"
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
            onClick={() => setDrawerOpen(false)}
          />
        )}

        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-800/80 bg-slate-950/95 backdrop-blur-xl transition-transform duration-300 lg:static lg:z-0 lg:w-64 lg:shrink-0 lg:translate-x-0",
            drawerOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
          )}
        >
          <div className="flex items-center justify-between border-b border-slate-800/80 px-4 py-3 lg:hidden">
            <span className="text-sm font-medium text-slate-300">Menu</span>
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="hidden border-b border-slate-800/80 px-4 py-4 lg:block">
            <p className="text-sm font-semibold text-white">Configurações</p>
            <p className="mt-0.5 text-xs text-slate-500">Base de conhecimento e biblioteca</p>
          </div>
          <div className="flex-1 overflow-y-auto">
            <SettingsNav onNavigate={() => setDrawerOpen(false)} />
          </div>
        </aside>

        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl p-4 sm:p-6">
            <header className="mb-6 hidden lg:block">
              <h2 className="text-xl font-semibold text-white">{settingsModule.label}</h2>
              <p className="mt-1 text-sm text-slate-500">{settingsModule.description}</p>
            </header>

            {knowledge?.error && (
              <div className="mb-6 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
                {knowledge.error}
              </div>
            )}

            {loading ? (
              <div className="flex min-h-[40vh] items-center justify-center">
                <LoadingSpinner label="Carregando configurações..." size="lg" />
              </div>
            ) : (
              children
            )}
          </div>
        </main>
      </div>
    </>
  );
}
