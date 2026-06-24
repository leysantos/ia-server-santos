"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type { BudgetSessionResponse, OpenCompositionDetail, PriceBankReference } from "@/types/api";
import OpenCompositionItemsTable from "@/components/OpenCompositionItemsTable";
import { BudgetTotalsDetailPanel } from "@/components/BudgetTotalsSummary";
import {
  compositionFetchKey,
  getAnaliticoUiState,
  getCachedComposition,
  loadBankReferencesCached,
  setAnaliticoUiState,
  setCachedComposition,
  type CachedCompositionEntry,
} from "@/lib/budget-analitico-cache";
import {
  buildAnaliticoTree,
  countAnaliticoServices,
  extractBudgetAnaliticoLines,
  flattenAnaliticoTree,
  formatBudgetBasesSummary,
  isSeminfCompositionCode,
  type AnaliticoGroupNode,
  type AnaliticoServiceNode,
  type ResolvePriceBaseOptions,
} from "@/lib/budget-analitico";
import { formatBrl, previewTotalSemd } from "@/lib/open-composition-ui";
import { budgetInput } from "@/lib/budget-ui";
import { cn } from "@/lib/utils";

interface BudgetAnaliticoTabProps {
  session: BudgetSessionResponse;
}

type CompositionLoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; detail: OpenCompositionDetail }
  | { status: "error"; message: string };

function toLoadState(entry: CachedCompositionEntry): CompositionLoadState {
  return entry;
}

function AnaliticoServiceCard({
  node,
  loadState,
  priceMode,
}: {
  node: AnaliticoServiceNode;
  loadState: CompositionLoadState;
  priceMode: "comd" | "semd";
}) {
  const { line } = node;
  const detail = loadState.status === "loaded" ? loadState.detail : null;

  return (
    <article className="overflow-hidden rounded-lg bg-slate-900/50 ring-1 ring-slate-700/60">
      <header className="border-b border-slate-700/50 bg-slate-900/70 px-4 py-3">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="font-mono text-xs text-cyan-400">{line.wbs_code}</span>
          <span className="font-mono text-xs text-slate-400">{line.composition_code}</span>
          <span className="text-sm font-medium text-slate-200">{line.description}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          <span>
            {line.quantity.toLocaleString("pt-BR", { maximumFractionDigits: 4 })} {line.unit}
          </span>
          <span>
            Unit. ComD: <span className="tabular-nums text-emerald-300/90">{formatBrl(line.unit_cost)}</span>
          </span>
          <span>
            Total ComD:{" "}
            <span className="tabular-nums text-emerald-300/90">{formatBrl(line.total_price)}</span>
          </span>
          <span>
            Total SemD:{" "}
            <span className="tabular-nums text-cyan-300/90">{formatBrl(line.total_price_semd)}</span>
          </span>
          <span>{line.base?.label ?? line.source_base ?? "—"}</span>
          {line.base?.reference && (
            <span className="text-slate-600">
              · {line.base.reference.replace(/^BR-/, "").replace(/-/g, "/")}
            </span>
          )}
        </div>
        {detail && (
          <div className="mt-2 flex flex-wrap gap-3 text-xs">
            <span className="rounded-md bg-emerald-500/10 px-2 py-1 text-emerald-200 ring-1 ring-emerald-500/20">
              CPU ComD: {formatBrl(detail.total_price)}
            </span>
            <span className="rounded-md bg-cyan-500/10 px-2 py-1 text-cyan-200 ring-1 ring-cyan-500/20">
              CPU SemD: {formatBrl(previewTotalSemd(detail))}
            </span>
            <span className="text-slate-500">{detail.items.length} item(ns) analítico(s)</span>
          </div>
        )}
      </header>

      <div className="bg-slate-950/30">
        {loadState.status === "loading" && (
          <p className="px-4 py-6 text-center text-xs text-slate-500">Carregando itens da CPU aberta…</p>
        )}
        {loadState.status === "error" && (
          <p className="px-4 py-6 text-center text-xs text-red-300">{loadState.message}</p>
        )}
        {loadState.status === "idle" && (
          <p className="px-4 py-6 text-center text-xs text-slate-500">Aguardando carregamento…</p>
        )}
        {detail && (
          <OpenCompositionItemsTable items={detail.items} priceMode={priceMode} compact />
        )}
      </div>
    </article>
  );
}

function AnaliticoGroupSection({
  node,
  depth,
  compositions,
  priceMode,
}: {
  node: AnaliticoGroupNode;
  depth: number;
  compositions: Map<string, CompositionLoadState>;
  priceMode: "comd" | "semd";
}) {
  const isEtapa = node.group.row_type === "ETAPA";
  const serviceCount = countAnaliticoServices(node);
  const border = isEtapa ? "ring-violet-500/30" : "ring-cyan-500/20";

  if (serviceCount === 0) return null;

  return (
    <section className={cn("overflow-hidden rounded-xl bg-slate-800/30 ring-1", border)}>
      <header
        className={cn(
          "border-b border-slate-700/50 bg-slate-900/40 px-4 py-3",
          depth > 0 && "pl-6"
        )}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "shrink-0 font-mono text-xs",
              isEtapa ? "text-violet-400" : "text-cyan-400"
            )}
          >
            {isEtapa ? "ETAPA" : "SUB-ETAPA"} {node.group.code}
          </span>
          <h3 className="truncate text-sm font-semibold uppercase text-white">{node.group.name}</h3>
        </div>
        <p className="mt-0.5 text-xs text-slate-500">{serviceCount} composição(ões) aberta(s)</p>
      </header>

      <div className={cn("space-y-3 p-4", depth > 0 && "pl-6")}>
        {node.services.length > 0 && (
          <div className="space-y-3">
            {node.services.map((item) => (
              <AnaliticoServiceCard
                key={item.line.row_id}
                node={item}
                loadState={compositions.get(item.line.row_id) ?? { status: "idle" }}
                priceMode={priceMode}
              />
            ))}
          </div>
        )}

        {node.subgroups.map((sub) => (
          <AnaliticoGroupSection
            key={sub.group.row_id}
            node={sub}
            depth={depth + 1}
            compositions={compositions}
            priceMode={priceMode}
          />
        ))}
      </div>
    </section>
  );
}

export default function BudgetAnaliticoTab({ session }: BudgetAnaliticoTabProps) {
  const sessionId = session.session_id;
  const savedUi = getAnaliticoUiState(sessionId);

  const rows = session.rows ?? [];
  const priceBases = session.project?.price_bases ?? [];
  const basePreco = session.project?.base_preco ?? "";
  const [bankReferences, setBankReferences] = useState<PriceBankReference[]>([]);

  const resolveOptions = useMemo<ResolvePriceBaseOptions>(
    () => ({ bankReferences, basePreco }),
    [bankReferences, basePreco]
  );

  useEffect(() => {
    let cancelled = false;
    void loadBankReferencesCached(async () => {
      const res = await api.pricingSyncBankReferences();
      return res.references ?? [];
    })
      .then((refs) => {
        if (!cancelled) setBankReferences(refs);
      })
      .catch(() => {
        if (!cancelled) setBankReferences([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const allLines = useMemo(
    () => extractBudgetAnaliticoLines(rows, priceBases, resolveOptions),
    [rows, priceBases, resolveOptions]
  );

  const [filterText, setFilterText] = useState(savedUi?.filterText ?? "");
  const [priceMode, setPriceMode] = useState<"comd" | "semd">(savedUi?.priceMode ?? "comd");
  const [compositions, setCompositions] = useState<Map<string, CompositionLoadState>>(new Map());
  const [loadProgress, setLoadProgress] = useState({ done: 0, total: 0 });

  useEffect(() => {
    setAnaliticoUiState(sessionId, { filterText, priceMode });
  }, [sessionId, filterText, priceMode]);

  const tree = useMemo(
    () => buildAnaliticoTree(rows, priceBases, filterText, resolveOptions),
    [rows, priceBases, filterText, resolveOptions]
  );

  const visibleServices = useMemo(() => flattenAnaliticoTree(tree), [tree]);

  const compositionLoadKey = useMemo(
    () =>
      visibleServices
        .map(
          (s) =>
            `${s.line.row_id}:${s.line.composition_code}:${s.line.base?.reference ?? ""}:${s.line.base?.uf ?? ""}`
        )
        .join("|"),
    [visibleServices]
  );

  useEffect(() => {
    if (visibleServices.length === 0) {
      setCompositions(new Map());
      setLoadProgress({ done: 0, total: 0 });
      return;
    }

    let cancelled = false;
    const services = visibleServices;

    async function loadCompositions() {
      const next = new Map<string, CompositionLoadState>();
      const pendingFetchKeys = new Set<string>();
      const fetchKeyByRowId = new Map<string, string>();

      for (const item of services) {
        const { line } = item;
        if (!line.base?.reference) {
          next.set(line.row_id, {
            status: "error",
            message: isSeminfCompositionCode(line.composition_code)
              ? "Base DP/SEMINF não encontrada. Importe em Configurações → Bases de preços ou adicione em Dados do orçamento."
              : "Base de preços não configurada para este serviço.",
          });
          continue;
        }

        const fetchKey = compositionFetchKey(
          line.composition_code,
          line.base.reference,
          line.base.uf
        );
        fetchKeyByRowId.set(line.row_id, fetchKey);

        const cached = getCachedComposition(fetchKey);
        if (cached) {
          next.set(line.row_id, toLoadState(cached));
        } else {
          pendingFetchKeys.add(fetchKey);
          next.set(line.row_id, { status: "loading" });
        }
      }

      const initialDone = [...next.values()].filter((s) => s.status !== "loading").length;
      setCompositions(new Map(next));
      setLoadProgress({ done: initialDone, total: services.length });

      if (pendingFetchKeys.size === 0 || cancelled) return;

      let done = initialDone;
      for (const fetchKey of pendingFetchKeys) {
        if (cancelled) return;

        const sample = services.find(
          (s) =>
            s.line.base?.reference &&
            compositionFetchKey(
              s.line.composition_code,
              s.line.base.reference,
              s.line.base.uf
            ) === fetchKey
        );
        if (!sample?.line.base?.reference) continue;

        const { line } = sample;
        try {
          const detail = await api.pricingSyncOpenComposition(line.composition_code, {
            uf: line.base.uf,
            reference: line.base.reference,
          });
          const entry: CachedCompositionEntry = { status: "loaded", detail };
          setCachedComposition(fetchKey, entry);
          for (const [rowId, key] of fetchKeyByRowId) {
            if (key === fetchKey) next.set(rowId, toLoadState(entry));
          }
        } catch (e) {
          const entry: CachedCompositionEntry = {
            status: "error",
            message:
              e instanceof Error
                ? e.message
                : `CPU aberta não encontrada para ${line.composition_code}`,
          };
          setCachedComposition(fetchKey, entry);
          for (const [rowId, key] of fetchKeyByRowId) {
            if (key === fetchKey) next.set(rowId, toLoadState(entry));
          }
        }

        done = [...next.values()].filter((s) => s.status !== "loading").length;
        if (!cancelled) {
          setCompositions(new Map(next));
          setLoadProgress({ done, total: services.length });
        }
      }
    }

    void loadCompositions();
    return () => {
      cancelled = true;
    };
  }, [compositionLoadKey, visibleServices]);

  const basesSummary = formatBudgetBasesSummary(priceBases);
  const loading = loadProgress.total > 0 && loadProgress.done < loadProgress.total;

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-slate-900/40 p-5 ring-1 ring-slate-800">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Orçamento analítico</h3>
            <p className="mt-1 text-xs text-slate-500">
              Composições abertas organizadas por etapa e sub-etapa, espelhando o orçamento sintético.
            </p>
            <p className="mt-2 text-xs text-cyan-400/90">{basesSummary}</p>
          </div>
          <label className="text-sm text-slate-400">
            Preços nos itens
            <select
              value={priceMode}
              onChange={(e) => setPriceMode(e.target.value as "comd" | "semd")}
              className="ml-2 rounded-lg border-0 bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-slate-700"
            >
              <option value="comd">Com desoneração (ComD)</option>
              <option value="semd">Sem desoneração (SemD)</option>
            </select>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="min-w-[min(100%,280px)] flex-1 text-sm text-slate-400">
            <span className="mb-1 block text-xs text-slate-500">Filtrar composições</span>
            <input
              type="text"
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder="Item, código da composição ou descrição…"
              className={cn(budgetInput, "w-full")}
            />
          </label>
          <span className="pb-2 text-xs text-slate-500">
            {visibleServices.length} de {allLines.length} composição(ões)
            {loading && ` · carregando ${loadProgress.done}/${loadProgress.total}`}
            {!loading && loadProgress.total > 0 && loadProgress.done === loadProgress.total && (
              <span className="text-slate-600"> · em cache</span>
            )}
          </span>
        </div>
      </div>

      {allLines.length === 0 && (
        <p className="rounded-xl bg-slate-900/40 px-4 py-10 text-center text-sm text-slate-500 ring-1 ring-slate-800">
          Nenhum serviço lançado no orçamento. Adicione composições em Etapas e composições ou
          importe a planilha PPD.
        </p>
      )}

      {allLines.length > 0 && visibleServices.length === 0 && (
        <p className="rounded-xl bg-slate-900/40 px-4 py-10 text-center text-sm text-slate-500 ring-1 ring-slate-800">
          Nenhuma composição corresponde ao filtro.
        </p>
      )}

      <div className="space-y-4">
        {tree.map((node) => (
          <AnaliticoGroupSection
            key={node.group.row_id}
            node={node}
            depth={0}
            compositions={compositions}
            priceMode={priceMode}
          />
        ))}
      </div>

      {allLines.length > 0 && (
        <BudgetTotalsDetailPanel session={session} />
      )}
    </div>
  );
}
