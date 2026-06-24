"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BudgetRow, BudgetSessionResponse } from "@/types/api";
import { cn } from "@/lib/utils";
import {
  modeColorClass,
  rowDualTotals,
} from "@/lib/budget-desoneracao";
import BudgetTotalsSummary from "@/components/BudgetTotalsSummary";
import {
  budgetBtn,
  budgetField,
  budgetFieldActionBtnCol,
  budgetFieldActionRow,
  budgetFieldLabel,
  budgetInput,
  budgetTextarea,
} from "@/lib/budget-ui";
import ModelSelector from "@/components/ModelSelector";
import { useLlmModelSelection } from "@/hooks/useLlmModel";

interface PriceHit {
  code?: string;
  description?: string;
  unit?: string;
  price?: number;
  source?: string;
}

interface BudgetEtapasPanelProps {
  session: BudgetSessionResponse;
  loading: boolean;
  onUpdate: (session: BudgetSessionResponse) => void;
  onError?: (err: unknown, title?: string) => void;
  onSave?: (context: { etapaCode: string; etapaName: string }) => Promise<void>;
}

function fmt(n: number) {
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function directServices(rows: BudgetRow[], groupCode: string): BudgetRow[] {
  return rows.filter(
    (r) =>
      r.row_type === "S" &&
      !r.is_memory_row &&
      r.parent_code === groupCode
  );
}

function subetapas(rows: BudgetRow[], parentCode: string): BudgetRow[] {
  return rows.filter((r) => r.row_type === "SUB-ETAPA" && r.parent_code === parentCode);
}

function GroupSection({
  group,
  rows,
  session,
  loading,
  depth,
  onUpdate,
  onError,
  onSave,
}: {
  group: BudgetRow;
  rows: BudgetRow[];
  session: BudgetSessionResponse;
  loading: boolean;
  depth: number;
  onUpdate: (s: BudgetSessionResponse) => void;
  onError?: (err: unknown, title?: string) => void;
  onSave?: (context: { etapaCode: string; etapaName: string }) => Promise<void>;
}) {
  const [editName, setEditName] = useState<{ code: string; name: string } | null>(null);
  const [newSubName, setNewSubName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [defaultQty, setDefaultQty] = useState("");
  const [manualQ, setManualQ] = useState("");
  const [manualQty, setManualQty] = useState("");
  const [hits, setHits] = useState<PriceHit[]>([]);
  const [searchParsedQty, setSearchParsedQty] = useState<number | null>(null);
  const [searching, setSearching] = useState(false);
  const [composing, setComposing] = useState(false);
  const [applyingQty, setApplyingQty] = useState(false);
  const [generatingMem, setGeneratingMem] = useState(false);
  const [savingEtapa, setSavingEtapa] = useState(false);
  const [etapaSavedFlash, setEtapaSavedFlash] = useState(false);
  const { model: llmModel, setModel: setLlmModel } = useLlmModelSelection();
  const composeModelId = `compose-model-${group.code}`;

  const services = directServices(rows, group.code);
  const children = subetapas(rows, group.code);
  const isEtapa = group.row_type === "ETAPA";

  useEffect(() => {
    if (manualQ.trim().length < 2) {
      setHits([]);
      setSearchParsedQty(null);
      return;
    }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await api.pricingSearchPrices(manualQ.trim(), 12, {
          sessionId: session.session_id,
          sourcePriority: session.source_priority,
        });
        setHits((res.results || []) as PriceHit[]);
        const pq = res.parsed_quantity ?? res.parsed?.quantity;
        setSearchParsedQty(pq != null && pq > 0 ? pq : null);
      } catch {
        setHits([]);
        setSearchParsedQty(null);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [manualQ, session.session_id, session.source_priority]);

  const handleCompose = async (replaceExisting = false) => {
    if (!prompt.trim()) return;
    setComposing(true);
    try {
      const qty = defaultQty.trim() ? parseFloat(defaultQty.replace(",", ".")) : undefined;
      const res = await api.pricingComposeEtapa(
        session.session_id,
        group.code,
        prompt,
        qty != null && !Number.isNaN(qty) ? qty : undefined,
        replaceExisting
      );
      onUpdate(res.session);
      if (replaceExisting) setPrompt("");
    } catch (err) {
      onError?.(err, replaceExisting ? "Erro ao recompor serviços" : "Erro ao compor serviços");
    } finally {
      setComposing(false);
    }
  };

  const handleLoadPrompt = async () => {
    try {
      const res = await api.pricingGetGroupComposePrompt(session.session_id, group.code);
      if (!res.prompt) {
        onError?.("Nenhum serviço lançado nesta etapa.", "Prompt vazio");
        return;
      }
      setPrompt(res.prompt);
    } catch (err) {
      onError?.(err, "Erro ao carregar serviços no prompt");
    }
  };

  const handleApplyQuantity = async () => {
    const qty = parseFloat(defaultQty.replace(",", "."));
    if (Number.isNaN(qty) || qty < 0) return;
    setApplyingQty(true);
    try {
      const res = await api.pricingApplyGroupQuantity(session.session_id, group.code, qty, true);
      onUpdate(res.session);
    } catch (err) {
      onError?.(err, "Erro ao aplicar quantidade");
    } finally {
      setApplyingQty(false);
    }
  };

  const handleQuantityChange = async (rowId: string, code: string, value: string) => {
    const qty = parseFloat(value.replace(",", "."));
    if (Number.isNaN(qty) || qty < 0) return;
    try {
      const updated = await api.pricingUpdateCell(session.session_id, {
        row_id: rowId,
        code,
        field: "quantity",
        value: qty,
      });
      onUpdate(updated);
    } catch (err) {
      onError?.(err, "Erro ao atualizar quantidade");
    }
  };

  const handleAddService = async (hit: PriceHit) => {
    const manualParsed = manualQty.trim() ? parseFloat(manualQty.replace(",", ".")) : undefined;
    const fromQuery = searchParsedQty ?? undefined;
    const qty = manualParsed != null && !Number.isNaN(manualParsed) ? manualParsed : fromQuery;
    try {
    const updated = await api.pricingAddService(session.session_id, {
      etapa_code: group.code,
      code: hit.code,
      description: hit.description,
      unit: hit.unit,
      price: hit.price,
      source: hit.source,
      ...(qty != null && !Number.isNaN(qty) ? { quantity: qty } : {}),
    });
    onUpdate(updated);
    setManualQ("");
    setManualQty("");
    setHits([]);
    setSearchParsedQty(null);
    } catch (err) {
      onError?.(err, "Erro ao adicionar serviço");
    }
  };

  const handleAddSub = async () => {
    const name = newSubName.trim().toUpperCase();
    if (!name) return;
    try {
    const updated = await api.pricingAddSubetapa(session.session_id, group.code, name);
    onUpdate(updated);
    setNewSubName("");
    } catch (err) {
      onError?.(err, "Erro ao adicionar sub-etapa");
    }
  };

  const handleSaveName = async () => {
    if (!editName) return;
    try {
    const updated = await api.pricingUpdateEtapa(
      session.session_id,
      editName.code,
      editName.name.trim().toUpperCase()
    );
    onUpdate(updated);
    setEditName(null);
    } catch (err) {
      onError?.(err, "Erro ao renomear etapa");
    }
  };

  const handleDelete = async (rowId: string) => {
    try {
    const updated = await api.pricingDeleteRow(session.session_id, rowId);
    onUpdate(updated);
    } catch (err) {
      onError?.(err, "Erro ao excluir linha");
    }
  };

  const handleGenerateMemory = async (useLlm: boolean) => {
    setGeneratingMem(true);
    try {
      const res = await api.pricingGenerateMemories(
        session.session_id,
        group.code,
        useLlm,
        useLlm ? llmModel : undefined
      );
      onUpdate(res.session);
    } catch (err) {
      onError?.(err, "Erro ao gerar memória de cálculo");
    } finally {
      setGeneratingMem(false);
    }
  };

  const handleSaveEtapa = async () => {
    if (!onSave || !isEtapa || depth !== 0) return;
    setSavingEtapa(true);
    setEtapaSavedFlash(false);
    try {
      await onSave({ etapaCode: group.code, etapaName: group.name });
      setEtapaSavedFlash(true);
      window.setTimeout(() => setEtapaSavedFlash(false), 2500);
    } catch (err) {
      onError?.(err, "Erro ao salvar etapa");
    } finally {
      setSavingEtapa(false);
    }
  };

  const border = depth === 0 ? "ring-violet-500/30" : "ring-cyan-500/20";

  return (
    <section className={`rounded-xl bg-slate-800/30 ring-1 ${border} overflow-hidden`}>
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700/50 bg-slate-900/40 px-4 py-3">
        <div className="flex min-h-10 min-w-0 flex-1 items-center gap-2">
          <span className={`shrink-0 text-xs font-mono ${isEtapa ? "text-violet-400" : "text-cyan-400"}`}>
            {isEtapa ? "ETAPA" : "SUB"} {group.code}
          </span>
          {editName?.code === group.code ? (
            <input
              autoFocus
              value={editName.name}
              onChange={(e) => setEditName({ ...editName, name: e.target.value.toUpperCase() })}
              className={cn(budgetInput, "uppercase")}
            />
          ) : (
            <h3 className="truncate text-sm font-semibold uppercase leading-10 text-white">{group.name}</h3>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editName?.code === group.code ? (
            <>
              <button type="button" onClick={handleSaveName} className={cn(budgetBtn, "text-emerald-300 ring-emerald-500/40 hover:bg-emerald-500/10")}>Salvar</button>
              <button type="button" onClick={() => setEditName(null)} className={cn(budgetBtn, "text-slate-400 ring-slate-600 hover:bg-slate-700/50")}>Cancelar</button>
            </>
          ) : (
            <>
              {isEtapa && depth === 0 && onSave && (
                <button
                  type="button"
                  disabled={loading || savingEtapa}
                  onClick={handleSaveEtapa}
                  className={cn(
                    budgetBtn,
                    "disabled:opacity-50",
                    etapaSavedFlash
                      ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
                      : "bg-indigo-600/20 text-indigo-300 ring-indigo-500/40 hover:bg-indigo-600/30"
                  )}
                  title="Persistir orçamento no banco (inclui esta etapa e demais alterações)"
                >
                  {savingEtapa ? "Salvando…" : etapaSavedFlash ? "Salvo ✓" : "Salvar"}
                </button>
              )}
              <button type="button" onClick={() => setEditName({ code: group.code, name: group.name })} className={cn(budgetBtn, "text-slate-300 ring-slate-600 hover:bg-slate-700/50")}>Editar</button>
              <button type="button" onClick={() => handleDelete(group.row_id)} className={cn(budgetBtn, "text-red-300 ring-red-500/30 hover:bg-red-500/10")}>Excluir</button>
              <button type="button" disabled={generatingMem} onClick={() => handleGenerateMemory(false)} className={cn(budgetBtn, "text-amber-300 ring-amber-500/40 hover:bg-amber-500/10 disabled:opacity-50")}>MC auto</button>
              <button type="button" disabled={generatingMem} onClick={() => handleGenerateMemory(true)} className={cn(budgetBtn, "text-violet-300 ring-violet-500/40 hover:bg-violet-500/10 disabled:opacity-50")}>MC IA</button>
            </>
          )}
        </div>
      </header>

      <div className="space-y-3 p-4">
        {isEtapa && (
          <div className={cn(budgetFieldActionRow, "rounded-lg bg-slate-900/40 p-3")}>
            <label className={cn(budgetField, "min-w-[180px] flex-1")}>
              <span className={budgetFieldLabel}>Nova sub-etapa</span>
              <input
                type="text"
                value={newSubName}
                onChange={(e) => setNewSubName(e.target.value.toUpperCase())}
                placeholder="Ex.: FUNDAÇÕES"
                className={cn(budgetInput, "uppercase")}
                onKeyDown={(e) => e.key === "Enter" && handleAddSub()}
              />
            </label>
            <div className={budgetFieldActionBtnCol}>
              <button
                type="button"
                disabled={loading || !newSubName.trim()}
                onClick={handleAddSub}
                className={cn(budgetBtn, "bg-cyan-600/20 text-cyan-300 ring-cyan-500/40 hover:bg-cyan-600/30")}
              >
                + Sub-etapa
              </button>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="text-xs text-slate-500">
              Composição — qtd.+unidade: <code className="text-cyan-400/80">(6 m)</code>,{" "}
              <code className="text-cyan-400/80">(6) (m)</code>, <code className="text-cyan-400/80">(m) (6)</code>,{" "}
              <code className="text-cyan-400/80">(6 mes)</code>, <code className="text-cyan-400/80">[12]</code>
            </label>
            <ModelSelector
              id={composeModelId}
              value={llmModel}
              onChange={setLlmModel}
              className="shrink-0"
            />
          </div>
          <textarea
            rows={Math.min(12, Math.max(3, prompt.split("\n").length + 1))}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={"base sicro\n(500 m²) pavimentação, (150 m²) pintura de ligação\n\nOu: (6 mes) engenheiro civil"}
            className={cn(budgetTextarea, "font-mono leading-relaxed")}
          />
          <div className="flex w-full flex-col gap-2 md:flex-row md:items-stretch">
            <input
              type="text"
              inputMode="decimal"
              value={defaultQty}
              onChange={(e) => setDefaultQty(e.target.value)}
              placeholder="Qtd. padrão (Ex.: 12)"
              title="Quantidade padrão da etapa"
              className={cn(budgetInput, "min-w-0 flex-1 text-center text-xs")}
            />
            <button
              type="button"
              disabled={loading || composing || !prompt.trim()}
              onClick={() => handleCompose(false)}
              className={cn(budgetBtn, "min-w-0 flex-1 bg-violet-600/20 text-violet-300 ring-violet-500/40 hover:bg-violet-600/30")}
            >
              {composing ? "Buscando…" : "Adicionar serviços"}
            </button>
            <button
              type="button"
              disabled={loading || composing || !prompt.trim()}
              onClick={() => handleCompose(true)}
              className={cn(budgetBtn, "min-w-0 flex-1 bg-emerald-600/20 text-emerald-300 ring-emerald-500/40 hover:bg-emerald-600/30")}
              title="Substitui todos os serviços desta etapa/sub-etapa pelo prompt"
            >
              {composing ? "Aplicando…" : "Recompor em lote"}
            </button>
            <button
              type="button"
              disabled={loading || services.length === 0}
              onClick={handleLoadPrompt}
              className={cn(budgetBtn, "min-w-0 flex-1 bg-slate-700/40 text-slate-300 ring-slate-600 hover:bg-slate-700/60")}
              title="Carrega os serviços lançados no prompt (um por linha)"
            >
              Carregar no prompt
            </button>
            <button
              type="button"
              disabled={loading || applyingQty || !defaultQty.trim()}
              onClick={handleApplyQuantity}
              className={cn(budgetBtn, "min-w-0 flex-1 bg-amber-600/20 text-amber-300 ring-amber-500/40 hover:bg-amber-600/30")}
              title="Aplica a quantidade padrão em todos os serviços desta etapa/sub-etapa"
            >
              {applyingQty ? "Aplicando…" : "Aplicar qtd. em todos"}
            </button>
          </div>
          <p className="text-xs text-slate-600">
            Um termo por linha. &quot;Carregar no prompt&quot; traz os serviços lançados para edição;
            &quot;Recompor em lote&quot; substitui todos os serviços da etapa.
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label className={cn(budgetField, "min-w-0 flex-1")}>
              <span className={budgetFieldLabel}>Busca manual (código ou descrição + unidade opcional)</span>
              <input
                type="text"
                value={manualQ}
                onChange={(e) => setManualQ(e.target.value)}
                placeholder="93567 ou concreto (4 m³)"
                className={budgetInput}
              />
            </label>
            <label className={cn(budgetField, "w-full sm:w-24")}>
              <span className={budgetFieldLabel}>Qtd.</span>
              <input
                type="text"
                inputMode="decimal"
                value={manualQty}
                onChange={(e) => setManualQty(e.target.value)}
                placeholder="1"
                className={cn(budgetInput, "text-center")}
              />
            </label>
          </div>
          {searching && <p className="text-xs text-slate-500">Filtrando base…</p>}
          {searchParsedQty != null && searchParsedQty > 0 && (
            <p className="text-xs text-cyan-500/80">
              Quantidade detectada na busca: {searchParsedQty}
              {manualQty.trim() ? " (campo Qtd. tem prioridade)" : ""}
            </p>
          )}
          {hits.length > 0 && (
            <ul className="max-h-40 overflow-y-auto rounded-lg ring-1 ring-slate-700/60 divide-y divide-slate-700/40">
              {hits.map((hit) => (
                <li key={`${hit.code}-${hit.description}`}>
                  <button type="button" onClick={() => handleAddService(hit)} className="w-full px-3 py-2 text-left text-xs hover:bg-cyan-500/10">
                    <span className="font-mono text-cyan-400">{hit.code}</span>
                    <span className="ml-2 text-slate-300">{hit.description}</span>
                    <span className="ml-2 text-slate-500">{hit.unit} · R$ {hit.price != null ? fmt(hit.price) : "—"}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {services.length > 0 && (
          <ServiceTable
            sessionId={session.session_id}
            sourcePriority={session.source_priority}
            services={services}
            onDelete={handleDelete}
            onQuantityChange={handleQuantityChange}
            onUpdate={onUpdate}
            onError={onError}
          />
        )}

        {children.map((sub) => (
          <div key={sub.row_id} className="ml-2 md:ml-4">
            <GroupSection
              group={sub}
              rows={rows}
              session={session}
              loading={loading}
              depth={depth + 1}
              onUpdate={onUpdate}
              onError={onError}
              onSave={onSave}
            />
          </div>
        ))}
      </div>
    </section>
  );
}

function PriceHitList({
  hits,
  onSelect,
}: {
  hits: PriceHit[];
  onSelect: (hit: PriceHit) => void;
}) {
  if (hits.length === 0) return null;
  return (
    <ul className="mt-1 max-h-36 overflow-y-auto rounded-lg ring-1 ring-slate-700/60 divide-y divide-slate-700/40">
      {hits.map((hit) => (
        <li key={`${hit.code}-${hit.description}`}>
          <button
            type="button"
            onClick={() => onSelect(hit)}
            className="w-full px-3 py-2 text-left text-xs hover:bg-cyan-500/10"
          >
            <span className="font-mono text-cyan-400">{hit.code}</span>
            <span className="ml-2 text-slate-300">{hit.description}</span>
            <span className="ml-2 text-slate-500">
              {hit.unit} · R$ {hit.price != null ? fmt(hit.price) : "—"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function ServiceTable({
  sessionId,
  sourcePriority,
  services,
  onDelete,
  onQuantityChange,
  onUpdate,
  onError,
}: {
  sessionId: string;
  sourcePriority?: string[];
  services: BudgetRow[];
  onDelete: (id: string) => void;
  onQuantityChange: (rowId: string, code: string, value: string) => void;
  onUpdate: (s: BudgetSessionResponse) => void;
  onError?: (err: unknown, title?: string) => void;
}) {
  const [replacingId, setReplacingId] = useState<string | null>(null);
  const [replaceQ, setReplaceQ] = useState("");
  const [replaceHits, setReplaceHits] = useState<PriceHit[]>([]);
  const [replaceSearching, setReplaceSearching] = useState(false);

  useEffect(() => {
    if (!replacingId || replaceQ.trim().length < 2) {
      setReplaceHits([]);
      return;
    }
    const t = setTimeout(async () => {
      setReplaceSearching(true);
      try {
        const res = await api.pricingSearchPrices(replaceQ.trim(), 12, {
          sessionId,
          sourcePriority,
        });
        setReplaceHits((res.results || []) as PriceHit[]);
      } catch {
        setReplaceHits([]);
      } finally {
        setReplaceSearching(false);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [replacingId, replaceQ, sessionId, sourcePriority]);

  const startReplace = (svc: BudgetRow) => {
    setReplacingId(svc.row_id);
    setReplaceQ((svc.pricing_query || svc.name.split("\n")[0] || "").trim());
    setReplaceHits([]);
  };

  const cancelReplace = () => {
    setReplacingId(null);
    setReplaceQ("");
    setReplaceHits([]);
  };

  const handleReplaceSelect = async (svc: BudgetRow, hit: PriceHit) => {
    try {
      const updated = await api.pricingReplaceService(sessionId, svc.row_id, {
        code: hit.code,
        description: hit.description,
        unit: hit.unit,
        price: hit.price,
        source: hit.source,
      });
      onUpdate(updated);
      cancelReplace();
    } catch (err) {
      onError?.(err, "Erro ao trocar serviço");
    }
  };

  return (
    <div className="overflow-x-auto rounded-lg ring-1 ring-slate-700/40">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-700/50">
            <th className="py-2 px-2">Item</th>
            <th className="py-2 px-2">Cód. base</th>
            <th className="py-2 px-2 min-w-[12rem]">Serviço</th>
            <th className="py-2 px-2">Und</th>
            <th className="py-2 px-2 text-right">Qtd</th>
            <th className="py-2 px-2 text-right">PU ComD</th>
            <th className="py-2 px-2 text-right">PU SemD</th>
            <th className="py-2 px-2 text-right">Total ComD</th>
            <th className="py-2 px-2 text-right">Total SemD</th>
            <th className="py-2 px-2" />
          </tr>
        </thead>
        <tbody>
          {services.map((svc) => {
            const { comd, semd } = rowDualTotals(svc);
            return (
            <Fragment key={svc.row_id}>
              <tr className="border-b border-slate-800/60 align-top">
                <td className="py-2 px-2 font-mono text-slate-400">{svc.code}</td>
                <td className="py-2 px-2 font-mono text-slate-500">{svc.source_code || "—"}</td>
                <td className="py-2 px-2 text-slate-200 min-w-[12rem] max-w-md whitespace-pre-wrap break-words leading-snug">
                  {svc.name}
                </td>
                <td className="py-2 px-2 text-slate-400">{svc.unit}</td>
                <td className="py-2 px-2 text-right">
                  <input
                    type="text"
                    inputMode="decimal"
                    defaultValue={svc.quantity ? String(svc.quantity) : ""}
                    key={`${svc.row_id}-${svc.quantity}`}
                    onBlur={(e) => {
                      const next = e.target.value.trim();
                      const prev = svc.quantity ? String(svc.quantity) : "";
                      if (next !== prev) {
                        onQuantityChange(svc.row_id, svc.code, next || "0");
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        (e.target as HTMLInputElement).blur();
                      }
                    }}
                    className="w-16 rounded bg-slate-900 px-1.5 py-0.5 text-right tabular-nums ring-1 ring-slate-600"
                  />
                </td>
                <td className={cn("py-2 px-2 text-right", modeColorClass("comd"))}>{fmt(svc.unit_price)}</td>
                <td className={cn("py-2 px-2 text-right", modeColorClass("semd"))}>{fmt(svc.unit_price_semd)}</td>
                <td className={cn("py-2 px-2 text-right", modeColorClass("comd"))}>{fmt(comd)}</td>
                <td className={cn("py-2 px-2 text-right", modeColorClass("semd"))}>{fmt(semd)}</td>
                <td className="py-2 px-2 whitespace-nowrap">
                  <button
                    type="button"
                    onClick={() => startReplace(svc)}
                    className="text-cyan-400 hover:text-cyan-300 mr-2"
                  >
                    Trocar
                  </button>
                  <button type="button" onClick={() => onDelete(svc.row_id)} className="text-red-400 hover:text-red-300">
                    Excluir
                  </button>
                </td>
              </tr>
              {replacingId === svc.row_id && (
                <tr className="bg-slate-900/60">
                  <td colSpan={10} className="px-3 py-3">
                    <label className="block space-y-1">
                      <span className="text-xs text-slate-500">Substituir serviço — digite código ou descrição</span>
                      <input
                        autoFocus
                        type="text"
                        value={replaceQ}
                        onChange={(e) => setReplaceQ(e.target.value)}
                        placeholder="93567 ou (4 m³) concreto"
                        className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm ring-1 ring-cyan-500/40"
                      />
                    </label>
                    {replaceSearching && <p className="mt-1 text-xs text-slate-500">Filtrando base…</p>}
                    <PriceHitList hits={replaceHits} onSelect={(hit) => handleReplaceSelect(svc, hit)} />
                    <button
                      type="button"
                      onClick={cancelReplace}
                      className="mt-2 text-xs text-slate-400 hover:text-slate-300"
                    >
                      Cancelar
                    </button>
                  </td>
                </tr>
              )}
            </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function BudgetEtapasPanel({ session, loading, onUpdate, onError, onSave }: BudgetEtapasPanelProps) {
  const etapas = useMemo(
    () => session.rows.filter((r) => r.row_type === "ETAPA" && r.level === 0),
    [session.rows]
  );
  const [newEtapaName, setNewEtapaName] = useState("");

  const handleAddEtapa = async () => {
    const name = newEtapaName.trim().toUpperCase();
    if (!name) return;
    try {
    const updated = await api.pricingAddEtapa(session.session_id, name);
    onUpdate(updated);
    setNewEtapaName("");
    } catch (err) {
      onError?.(err, "Erro ao adicionar etapa");
    }
  };

  return (
    <div className="space-y-4">
      <div className={cn(budgetFieldActionRow, "rounded-xl bg-slate-800/20 p-4 ring-1 ring-slate-700/40")}>
        <label className={cn(budgetField, "min-w-[240px] flex-1")}>
          <span className={budgetFieldLabel}>Nova etapa</span>
          <input
            type="text"
            value={newEtapaName}
            onChange={(e) => setNewEtapaName(e.target.value.toUpperCase())}
            placeholder="Ex.: ADMINISTRAÇÃO DA OBRA"
            className={cn(budgetInput, "uppercase")}
            onKeyDown={(e) => e.key === "Enter" && handleAddEtapa()}
          />
        </label>
        <div className={budgetFieldActionBtnCol}>
          <button
            type="button"
            disabled={loading || !newEtapaName.trim()}
            onClick={handleAddEtapa}
            className={cn(budgetBtn, "bg-cyan-600/20 px-4 text-cyan-300 ring-cyan-500/40 hover:bg-cyan-600/30")}
          >
            + Etapa
          </button>
        </div>
      </div>

      {etapas.length === 0 && (
        <p className="text-center text-sm text-slate-500 py-8">
          Adicione etapas ou importe um template de modelo.
        </p>
      )}

      {etapas.map((etapa) => (
        <GroupSection
          key={etapa.row_id}
          group={etapa}
          rows={session.rows}
          session={session}
          loading={loading}
          depth={0}
          onUpdate={onUpdate}
          onError={onError}
          onSave={onSave}
        />
      ))}

      <div className="rounded-xl bg-slate-900/50 px-4 py-3 ring-1 ring-slate-700/40">
        <BudgetTotalsSummary session={session} compact />
      </div>
    </div>
  );
}
