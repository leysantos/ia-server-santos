"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "@/services/api";
import type { BudgetSkeleton } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetBtn, budgetField, budgetFieldLabel, budgetInput } from "@/lib/budget-ui";
import LoadingSpinner from "@/components/LoadingSpinner";

const PANEL_W = 420;
const PANEL_H_EST = 340;

const BLANK_VALUE = "__blank__";

export interface BudgetNewModalProps {
  open: boolean;
  obraType: string;
  loading?: boolean;
  onClose: () => void;
  onSelectBlank: () => void;
  onSelectSkeleton: (skeleton: BudgetSkeleton, projeto: string) => void;
}

export default function BudgetNewModal({
  open,
  obraType,
  loading = false,
  onClose,
  onSelectBlank,
  onSelectSkeleton,
}: BudgetNewModalProps) {
  const [skeletons, setSkeletons] = useState<BudgetSkeleton[]>([]);
  const [fetching, setFetching] = useState(false);
  const [projeto, setProjeto] = useState("");
  const [search, setSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [selection, setSelection] = useState<string>(BLANK_VALUE);
  const [pos, setPos] = useState({ x: 80, y: 80 });
  const [mounted, setMounted] = useState(false);

  const dragRef = useRef<{
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);
  const comboboxRef = useRef<HTMLDivElement>(null);
  const inputAnchorRef = useRef<HTMLDivElement>(null);
  const dropdownPortalRef = useRef<HTMLUListElement>(null);
  const [menuRect, setMenuRect] = useState<{
    top: number;
    left: number;
    width: number;
    maxHeight: number;
  } | null>(null);

  const updateMenuPosition = useCallback(() => {
    const el = inputAnchorRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const gap = 4;
    const spaceBelow = window.innerHeight - rect.bottom - gap - 8;
    const spaceAbove = rect.top - gap - 8;
    const preferredMax = 240;
    const openUp = spaceBelow < 160 && spaceAbove > spaceBelow;
    const maxHeight = Math.min(preferredMax, openUp ? spaceAbove : spaceBelow);
    setMenuRect({
      top: openUp ? rect.top - gap - maxHeight : rect.bottom + gap,
      left: rect.left,
      width: rect.width,
      maxHeight: Math.max(120, maxHeight),
    });
  }, []);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    setFetching(true);
    api
      .pricingListSkeletons()
      .then((r) => setSkeletons(r.items))
      .catch(() => setSkeletons([]))
      .finally(() => setFetching(false));
  }, [open]);

  useEffect(() => {
    if (!open) {
      setProjeto("");
      setSearch("");
      setSelection(BLANK_VALUE);
      setDropdownOpen(false);
      return;
    }
    const x = Math.max(16, (window.innerWidth - PANEL_W) / 2);
    const y = Math.max(16, (window.innerHeight - PANEL_H_EST) / 2);
    setPos({ x, y });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!dropdownOpen) {
      setMenuRect(null);
      return;
    }
    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [dropdownOpen, updateMenuPosition, pos]);

  useEffect(() => {
    if (!dropdownOpen) return;
    const onDoc = (e: MouseEvent) => {
      const target = e.target as Node;
      if (comboboxRef.current?.contains(target)) return;
      if (dropdownPortalRef.current?.contains(target)) return;
      setDropdownOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [dropdownOpen]);

  const onHeaderMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if ((e.target as HTMLElement).closest("button")) return;
      e.preventDefault();
      dragRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        originX: pos.x,
        originY: pos.y,
      };
    },
    [pos.x, pos.y]
  );

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragRef.current) return;
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      const maxX = Math.max(0, window.innerWidth - PANEL_W - 8);
      const maxY = Math.max(0, window.innerHeight - 120);
      setPos({
        x: Math.min(maxX, Math.max(8, dragRef.current.originX + dx)),
        y: Math.min(maxY, Math.max(8, dragRef.current.originY + dy)),
      });
    };
    const onUp = () => {
      dragRef.current = null;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return skeletons;
    return skeletons.filter(
      (sk) =>
        sk.name.toLowerCase().includes(q) ||
        (sk.description || "").toLowerCase().includes(q) ||
        sk.obra_type.toLowerCase().includes(q)
    );
  }, [skeletons, search]);

  const selectedSkeleton =
    selection !== BLANK_VALUE ? skeletons.find((s) => s.id === selection) : null;

  const displayLabel =
    selection === BLANK_VALUE
      ? "Orçamento em branco"
      : selectedSkeleton?.name ?? "";

  const pickOption = (value: string, label: string) => {
    setSelection(value);
    setSearch(value === BLANK_VALUE ? "" : label);
    setDropdownOpen(false);
  };

  const handleCreate = () => {
    if (selection === BLANK_VALUE) {
      onSelectBlank();
      return;
    }
    if (selectedSkeleton) {
      onSelectSkeleton(selectedSkeleton, projeto.trim());
    }
  };

  if (!open || !mounted) return null;

  const dropdownMenu =
    dropdownOpen && !fetching && menuRect
      ? createPortal(
          <ul
            ref={dropdownPortalRef}
            id="budget-skeleton-listbox"
            role="listbox"
            className="fixed z-[70] overflow-y-auto rounded-lg border border-white/10 bg-surface-card py-1 shadow-glow ring-1 ring-white/10"
            style={{
              top: menuRect.top,
              left: menuRect.left,
              width: menuRect.width,
              maxHeight: menuRect.maxHeight,
            }}
          >
            <li role="option" aria-selected={selection === BLANK_VALUE}>
              <button
                type="button"
                className={cn(
                  "w-full px-3 py-2 text-left text-sm transition-colors",
                  selection === BLANK_VALUE
                    ? "bg-brand-500/15 text-brand-200"
                    : "text-slate-300 hover:bg-white/5"
                )}
                onClick={() => pickOption(BLANK_VALUE, "Orçamento em branco")}
              >
                <span className="font-medium">Orçamento em branco</span>
                <span className="mt-0.5 block text-xs text-slate-500">Sem etapas pré-definidas</span>
              </button>
            </li>
            {filtered.length === 0 ? (
              <li className="px-3 py-3 text-center text-xs text-slate-500">
                {search.trim() ? "Nenhum modelo encontrado" : "Digite para buscar modelos"}
              </li>
            ) : (
              filtered.map((sk) => (
                <li key={sk.id} role="option" aria-selected={selection === sk.id}>
                  <button
                    type="button"
                    className={cn(
                      "w-full px-3 py-2 text-left text-sm transition-colors",
                      selection === sk.id
                        ? "bg-brand-500/15 text-brand-200"
                        : "text-slate-300 hover:bg-white/5"
                    )}
                    onClick={() => pickOption(sk.id, sk.name)}
                  >
                    <span className="font-medium">{sk.name}</span>
                    <span className="mt-0.5 block text-xs text-slate-500">
                      {sk.etapas.length} etapa(s) · {sk.obra_type}
                      {sk.description ? ` · ${sk.description}` : ""}
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>,
          document.body
        )
      : null;

  const panel = (
    <div
      role="dialog"
      aria-modal="false"
      aria-labelledby="budget-new-title"
      className="pointer-events-none fixed inset-0 z-[60]"
    >
      <div
        className="app-card pointer-events-auto absolute flex w-[420px] flex-col overflow-visible shadow-glow ring-1 ring-white/10"
        style={{ left: pos.x, top: pos.y }}
      >
        <div
          className="flex cursor-grab items-start justify-between gap-2 border-b border-white/5 bg-surface-elevated/80 px-4 py-3 active:cursor-grabbing"
          onMouseDown={onHeaderMouseDown}
        >
          <div className="min-w-0 select-none">
            <h2 id="budget-new-title" className="text-sm font-semibold text-white">
              Novo orçamento
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Arraste pela barra · tipo obra padrão: {obraType}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="shrink-0 rounded-lg px-2 py-1 text-slate-500 hover:bg-white/5 hover:text-slate-200"
            aria-label="Fechar"
          >
            ×
          </button>
        </div>

        <div className="space-y-4 px-4 py-4">
          <div className={budgetField}>
            <label className={budgetFieldLabel} htmlFor="budget-new-projeto">
              Nome do projeto (opcional)
            </label>
            <input
              id="budget-new-projeto"
              value={projeto}
              onChange={(e) => setProjeto(e.target.value)}
              placeholder="Ex.: Reforma quadra municipal Centro"
              className={budgetInput}
              disabled={loading}
            />
          </div>

          <div className={budgetField} ref={comboboxRef}>
            <label className={budgetFieldLabel} htmlFor="budget-new-skeleton-search">
              Modelo de esqueleto
            </label>
            <div className="relative" ref={inputAnchorRef}>
              <input
                id="budget-new-skeleton-search"
                value={dropdownOpen ? search : displayLabel}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setDropdownOpen(true);
                  if (!e.target.value.trim()) setSelection(BLANK_VALUE);
                  requestAnimationFrame(updateMenuPosition);
                }}
                onFocus={() => {
                  setSearch(displayLabel === "Orçamento em branco" ? "" : displayLabel);
                  setDropdownOpen(true);
                  requestAnimationFrame(updateMenuPosition);
                }}
                placeholder="Buscar modelo cadastrado..."
                className={budgetInput}
                disabled={loading || fetching}
                autoComplete="off"
                role="combobox"
                aria-expanded={dropdownOpen}
                aria-controls="budget-skeleton-listbox"
              />
              <button
                type="button"
                tabIndex={-1}
                disabled={loading || fetching}
                onClick={() => {
                  setDropdownOpen((v) => {
                    const next = !v;
                    if (next) updateMenuPosition();
                    return next;
                  });
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                aria-label="Abrir lista"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
            {fetching && <LoadingSpinner label="Carregando modelos..." size="sm" />}
          </div>

          {selectedSkeleton && (
            <div className="rounded-lg border border-white/5 bg-surface-elevated/60 px-3 py-2 text-xs text-slate-400">
              <span className="font-medium text-slate-300">{selectedSkeleton.name}</span>
              {selectedSkeleton.description && (
                <p className="mt-1 line-clamp-2">{selectedSkeleton.description}</p>
              )}
              <p className="mt-1 text-[10px] text-slate-600">
                {selectedSkeleton.etapas.length} etapa(s) · BDI {selectedSkeleton.obra_type}
              </p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-white/5 px-4 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className={cn(budgetBtn, "px-3 text-xs text-slate-400 hover:bg-white/5")}
          >
            Cancelar
          </button>
          <button
            type="button"
            disabled={loading || (selection !== BLANK_VALUE && !selectedSkeleton)}
            onClick={handleCreate}
            className={cn(
              budgetBtn,
              "bg-brand-600/20 px-4 text-xs text-brand-200 hover:bg-brand-600/30 disabled:opacity-40"
            )}
          >
            {loading ? "Criando..." : "Criar orçamento"}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {createPortal(panel, document.body)}
      {dropdownMenu}
    </>
  );
}
