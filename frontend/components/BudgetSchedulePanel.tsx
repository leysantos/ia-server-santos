"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type {
  BudgetSessionResponse,
  ProjectSchedule,
  ScheduleLink,
  ScheduleTask,
} from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetBtn, budgetField, budgetFieldLabel, budgetInput, budgetTextarea } from "@/lib/budget-ui";
import { formatIsoDateBr, type ScheduleViewMode } from "@/lib/schedule-curves";
import BudgetGantt from "@/components/BudgetGantt";
import ModelSelector from "@/components/ModelSelector";
import { useLlmModelSelection } from "@/hooks/useLlmModel";

const LINK_TYPES = ["FS", "SS", "FF", "SF"] as const;
type LinkType = (typeof LINK_TYPES)[number];

interface BudgetSchedulePanelProps {
  session: BudgetSessionResponse;
  loading?: boolean;
  onUpdate: (session: BudgetSessionResponse) => void;
  onError?: (err: unknown, title?: string) => void;
}

export default function BudgetSchedulePanel({
  session,
  loading,
  onUpdate,
  onError,
}: BudgetSchedulePanelProps) {
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [projectStart, setProjectStart] = useState(
    session.schedule?.project_start || new Date().toISOString().slice(0, 10)
  );
  const [durationDraft, setDurationDraft] = useState("");
  const [predDraft, setPredDraft] = useState("");
  const [succDraft, setSuccDraft] = useState("");
  const [predLinkType, setPredLinkType] = useState<LinkType>("FS");
  const [succLinkType, setSuccLinkType] = useState<LinkType>("FS");
  const [predLag, setPredLag] = useState("0");
  const [succLag, setSuccLag] = useState("0");
  const [viewMode, setViewMode] = useState<ScheduleViewMode>("completo");
  const [agentPrompt, setAgentPrompt] = useState("");
  const [replaceLinks, setReplaceLinks] = useState(false);
  const [agentSummary, setAgentSummary] = useState<string | null>(null);
  const [composing, setComposing] = useState(false);
  const { model: llmModel, setModel: setLlmModel } = useLlmModelSelection();

  const schedule = session.schedule;

  useEffect(() => {
    if (session.schedule?.project_start) {
      setProjectStart(session.schedule.project_start);
    }
  }, [session.schedule?.project_start]);

  useEffect(() => {
    if (!schedule && session.session_id && !loading) {
      void handleSync();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.session_id]);

  const leafTasks = useMemo(
    () => schedule?.tasks.filter((t) => !t.is_summary) ?? [],
    [schedule]
  );

  const selected = useMemo(
    () => schedule?.tasks.find((t) => t.task_id === selectedId) ?? null,
    [schedule, selectedId]
  );

  useEffect(() => {
    if (selected && !selected.is_summary) {
      setDurationDraft(String(selected.duration_days));
      setPredDraft("");
      setSuccDraft("");
      setPredLinkType("FS");
      setSuccLinkType("FS");
      setPredLag("0");
      setSuccLag("0");
    }
  }, [selected]);

  const run = useCallback(
    async (fn: () => Promise<BudgetSessionResponse>, title?: string) => {
      setBusy(true);
      try {
        const updated = await fn();
        onUpdate(updated);
      } catch (err) {
        onError?.(err, title);
      } finally {
        setBusy(false);
      }
    },
    [onUpdate, onError]
  );

  const handleSync = () =>
    run(() => api.pricingSyncSchedule(session.session_id), "Erro ao sincronizar cronograma");

  const handleRecalc = () =>
    run(() => api.pricingRecalculateSchedule(session.session_id), "Erro ao recalcular CPM");

  const handleStartDate = () =>
    run(
      () => api.pricingUpdateScheduleSettings(session.session_id, projectStart),
      "Erro ao atualizar data de início"
    );

  const handleDuration = () => {
    if (!selected || selected.is_summary) return;
    const d = parseInt(durationDraft, 10);
    if (Number.isNaN(d) || d < 1) return;
    run(
      () => api.pricingUpdateScheduleTask(session.session_id, selected.task_id, { duration_days: d }),
      "Erro ao atualizar duração"
    );
  };

  const handleAddPredecessor = () => {
    if (!selected || !predDraft || selected.is_summary) return;
    const lag = parseInt(predLag, 10);
    run(
      () =>
        api.pricingAddScheduleLink(session.session_id, {
          predecessor_id: predDraft,
          successor_id: selected.task_id,
          link_type: predLinkType,
          lag_days: Number.isNaN(lag) ? 0 : Math.max(0, lag),
        }),
      "Erro ao adicionar predecessor"
    );
    setPredDraft("");
    setPredLag("0");
  };

  const handleAddSuccessor = () => {
    if (!selected || !succDraft || selected.is_summary) return;
    const lag = parseInt(succLag, 10);
    run(
      () =>
        api.pricingAddScheduleLink(session.session_id, {
          predecessor_id: selected.task_id,
          successor_id: succDraft,
          link_type: succLinkType,
          lag_days: Number.isNaN(lag) ? 0 : Math.max(0, lag),
        }),
      "Erro ao adicionar sucessora"
    );
    setSuccDraft("");
    setSuccLag("0");
  };

  const handleRemoveLink = (linkId: string) =>
    run(() => api.pricingDeleteScheduleLink(session.session_id, linkId), "Erro ao remover vínculo");

  const handleComposeSchedule = async () => {
    if (!agentPrompt.trim() || !schedule) return;
    setComposing(true);
    setAgentSummary(null);
    const prompt = agentPrompt.trim();
    const autoReplaceLinks =
      replaceLinks ||
      /reorganiz|ajuste completo|refazer|do zero|sequenciar tod|ordem de execu|ordem correta|cronograma completo/i.test(
        prompt
      );
    try {
      const res = await api.pricingComposeSchedule(session.session_id, prompt, {
        useLlm: true,
        replaceLinks: autoReplaceLinks,
        llmModel,
      });
      onUpdate(res.session);
      const ok = res.schedule_log.filter((l) => l.status === "ok").length;
      const skipped = res.schedule_log.filter((l) => l.status === "skip").length;
      const errEntries = res.schedule_log.filter((l) => l.status === "error");
      const err = errEntries.length;
      const errDetail =
        err > 0
          ? ` · erros: ${errEntries.map((e) => `${e.action} (${e.detail || "?"})`).join("; ")}`
          : "";
      setAgentSummary(
        `${res.summary}${res.llm_model ? ` · modelo: ${res.llm_model}` : ""} · ${ok} ok` +
          (skipped ? ` · ${skipped} ignorada(s)` : "") +
          (err ? ` · ${err} erro(s)${errDetail}` : "") +
          (autoReplaceLinks && !replaceLinks ? " · vínculos substituídos (auto)" : "")
      );
    } catch (err) {
      onError?.(err, "Erro ao organizar cronograma com IA");
    } finally {
      setComposing(false);
    }
  };

  const predecessorLinks = useMemo(() => {
    if (!schedule || !selected) return [];
    return schedule.links.filter((l) => l.successor_id === selected.task_id);
  }, [schedule, selected]);

  const successorLinks = useMemo(() => {
    if (!schedule || !selected) return [];
    return schedule.links.filter((l) => l.predecessor_id === selected.task_id);
  }, [schedule, selected]);

  const taskById = useMemo(() => {
    const map = new Map<string, ScheduleTask>();
    schedule?.tasks.forEach((t) => map.set(t.task_id, t));
    return map;
  }, [schedule]);

  const taskLabel = (taskId: string) => {
    const t = taskById.get(taskId);
    return t ? `${t.budget_code} — ${t.name}` : taskId.slice(0, 8);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1.5">
      <section className="flex shrink-0 flex-wrap items-center gap-x-2 gap-y-1 rounded-lg bg-slate-800/40 px-2 py-1.5 ring-1 ring-slate-700/60">
        <label className={cn(budgetField, "w-[140px]")}>
          <span className={budgetFieldLabel}>Início da obra</span>
          <input
            type="date"
            value={projectStart}
            onChange={(e) => setProjectStart(e.target.value)}
            className={budgetInput}
          />
        </label>
        <div className="flex shrink-0 items-end gap-1 pt-4">
          <button
            type="button"
            disabled={loading || busy}
            onClick={handleStartDate}
            className={cn(budgetBtn, "bg-slate-700/50 text-slate-200 ring-slate-600 hover:bg-slate-700/70")}
          >
            Aplicar
          </button>
          <button
            type="button"
            disabled={loading || busy}
            onClick={handleSync}
            className={cn(budgetBtn, "bg-cyan-600/20 text-cyan-300 ring-cyan-500/40 hover:bg-cyan-600/30")}
          >
            Sincronizar
          </button>
          <button
            type="button"
            disabled={loading || busy || !schedule}
            onClick={handleRecalc}
            className={cn(budgetBtn, "bg-violet-600/20 text-violet-300 ring-violet-500/40 hover:bg-violet-600/30")}
          >
            CPM
          </button>
        </div>

        <div className="flex shrink-0 items-end gap-1 pt-4">
          {(["etapas", "completo"] as ScheduleViewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              className={cn(
                budgetBtn,
                viewMode === mode
                  ? "bg-cyan-600/30 text-cyan-200 ring-cyan-400/50"
                  : "bg-slate-800/50 text-slate-400 ring-slate-600 hover:text-slate-200"
              )}
            >
              {mode === "etapas" ? "Etapas" : "Completo"}
            </button>
          ))}
        </div>

        {schedule?.project_end && (
          <p className="text-[10px] text-slate-500 sm:ml-auto">
            Término: <span className="text-emerald-400">{formatIsoDateBr(schedule.project_end)}</span>
            {" · "}
            {leafTasks.filter((t) => t.is_critical).length} crítica(s)
          </p>
        )}

        <div className="hidden flex-wrap gap-2 text-[9px] text-slate-500 xl:flex">
          <LegendDot color="bg-red-600/80" label="Crítico" />
          <LegendDot color="bg-cyan-600/70" label="Folga" />
          <LegendDot color="bg-violet-600/50" label="Resumo" />
          <LegendDot color="bg-emerald-500/50" label="Físico" />
          <LegendDot color="bg-amber-500/55" label="Desembolso" />
          <LegendDot color="bg-cyan-500/40" label="Acum." />
        </div>
      </section>

      {!schedule || schedule.tasks.length === 0 ? (
        <p className="rounded-xl bg-slate-800/40 px-4 py-8 text-center text-sm text-slate-500 ring-1 ring-slate-700/60">
          Adicione serviços nas etapas e clique em &quot;Sincronizar&quot;.
        </p>
      ) : (
        <>
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <BudgetGantt
              schedule={schedule}
              budgetRows={session.rows}
              viewMode={viewMode}
              selectedTaskId={selectedId}
              onSelectTask={setSelectedId}
            />
          </div>

          <section className="grid max-h-[min(42vh,320px)] shrink-0 grid-cols-1 gap-0 overflow-y-auto rounded-lg bg-slate-800/40 ring-1 ring-slate-700/60 lg:grid-cols-2 lg:divide-x lg:divide-slate-700/50">
            <ScheduleAgentPanel
              agentPrompt={agentPrompt}
              replaceLinks={replaceLinks}
              agentSummary={agentSummary}
              composing={composing}
              llmModel={llmModel}
              loading={!!loading}
              busy={busy}
              onPromptChange={setAgentPrompt}
              onReplaceLinksChange={setReplaceLinks}
              onModelChange={setLlmModel}
              onCompose={() => void handleComposeSchedule()}
            />

            {selected && !selected.is_summary ? (
              <TaskEditor
                task={selected}
                durationDraft={durationDraft}
                predDraft={predDraft}
                succDraft={succDraft}
                predLinkType={predLinkType}
                succLinkType={succLinkType}
                predLag={predLag}
                succLag={succLag}
                leafTasks={leafTasks}
                predecessorLinks={predecessorLinks}
                successorLinks={successorLinks}
                taskLabel={taskLabel}
                busy={busy || !!loading}
                onDurationChange={setDurationDraft}
                onPredChange={setPredDraft}
                onSuccChange={setSuccDraft}
                onPredLinkTypeChange={setPredLinkType}
                onSuccLinkTypeChange={setSuccLinkType}
                onPredLagChange={setPredLag}
                onSuccLagChange={setSuccLag}
                onSaveDuration={handleDuration}
                onAddPredecessor={handleAddPredecessor}
                onAddSuccessor={handleAddSuccessor}
                onRemoveLink={handleRemoveLink}
              />
            ) : (
              <div className="flex items-center justify-center p-4 text-center text-[11px] text-slate-500">
                {selected?.is_summary
                  ? "Selecione um serviço folha para edição manual de duração e vínculos."
                  : "Clique em uma tarefa no Gantt para editar manualmente, ou use o agente IA ao lado."}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={cn("inline-block h-2 w-4 rounded", color)} />
      {label}
    </span>
  );
}

function ScheduleAgentPanel({
  agentPrompt,
  replaceLinks,
  agentSummary,
  composing,
  llmModel,
  loading,
  busy,
  onPromptChange,
  onReplaceLinksChange,
  onModelChange,
  onCompose,
}: {
  agentPrompt: string;
  replaceLinks: boolean;
  agentSummary: string | null;
  composing: boolean;
  llmModel: string;
  loading: boolean;
  busy: boolean;
  onPromptChange: (v: string) => void;
  onReplaceLinksChange: (v: boolean) => void;
  onModelChange: (v: string) => void;
  onCompose: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-col gap-2 p-3">
      <label className={budgetField}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className={budgetFieldLabel}>Comando do cronograma</span>
          <ModelSelector
            id="schedule-agent-model"
            value={llmModel}
            onChange={onModelChange}
            className="shrink-0"
          />
        </div>
        <textarea
          value={agentPrompt}
          onChange={(e) => onPromptChange(e.target.value)}
          rows={2}
          placeholder='Ex: "reorganizar cronograma completo", "administração durante toda a obra", "2.3 duração 45 dias"'
          className={cn(budgetTextarea, "min-h-[52px] resize-none text-sm")}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              onCompose();
            }
          }}
        />
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 text-[10px] text-slate-400">
          <input
            type="checkbox"
            checked={replaceLinks}
            onChange={(e) => onReplaceLinksChange(e.target.checked)}
            className="rounded border-slate-600 bg-slate-900"
          />
          Substituir vínculos
        </label>
        <button
          type="button"
          disabled={loading || busy || composing || !agentPrompt.trim()}
          onClick={onCompose}
          className={cn(
            budgetBtn,
            "ml-auto bg-violet-600/25 text-violet-200 ring-violet-500/40 hover:bg-violet-600/35"
          )}
        >
          {composing ? "Organizando…" : "Organizar com IA"}
        </button>
      </div>

      {agentSummary ? (
        <p className="rounded bg-slate-900/60 px-2 py-1 text-[10px] leading-snug text-emerald-300">
          {agentSummary}
        </p>
      ) : (
        <p className="text-[9px] text-slate-600">Ctrl+Enter para aplicar</p>
      )}
    </div>
  );
}

function TaskEditor({
  task,
  durationDraft,
  predDraft,
  succDraft,
  predLinkType,
  succLinkType,
  predLag,
  succLag,
  leafTasks,
  predecessorLinks,
  successorLinks,
  taskLabel,
  busy,
  onDurationChange,
  onPredChange,
  onSuccChange,
  onPredLinkTypeChange,
  onSuccLinkTypeChange,
  onPredLagChange,
  onSuccLagChange,
  onSaveDuration,
  onAddPredecessor,
  onAddSuccessor,
  onRemoveLink,
}: {
  task: ScheduleTask;
  durationDraft: string;
  predDraft: string;
  succDraft: string;
  predLinkType: LinkType;
  succLinkType: LinkType;
  predLag: string;
  succLag: string;
  leafTasks: ScheduleTask[];
  predecessorLinks: ScheduleLink[];
  successorLinks: ScheduleLink[];
  taskLabel: (id: string) => string;
  busy: boolean;
  onDurationChange: (v: string) => void;
  onPredChange: (v: string) => void;
  onSuccChange: (v: string) => void;
  onPredLinkTypeChange: (v: LinkType) => void;
  onSuccLinkTypeChange: (v: LinkType) => void;
  onPredLagChange: (v: string) => void;
  onSuccLagChange: (v: string) => void;
  onSaveDuration: () => void;
  onAddPredecessor: () => void;
  onAddSuccessor: () => void;
  onRemoveLink: (linkId: string) => void;
}) {
  const predCandidates = leafTasks.filter(
    (t) =>
      t.task_id !== task.task_id &&
      !predecessorLinks.some((l) => l.predecessor_id === t.task_id)
  );
  const succCandidates = leafTasks.filter(
    (t) =>
      t.task_id !== task.task_id &&
      !successorLinks.some((l) => l.successor_id === t.task_id)
  );

  return (
    <div className="flex min-h-0 flex-col gap-2 overflow-y-auto p-3">
      <h3 className="truncate text-[11px] font-medium text-cyan-400">
        Edição manual — {task.budget_code} {task.name}
      </h3>

      <div className="flex flex-wrap items-end gap-2">
        <label className={cn(budgetField, "w-[88px]")}>
          <span className={budgetFieldLabel}>Duração (d)</span>
          <input
            type="number"
            min={1}
            value={durationDraft}
            onChange={(e) => onDurationChange(e.target.value)}
            className={budgetInput}
          />
        </label>
        <button
          type="button"
          disabled={busy}
          onClick={onSaveDuration}
          className={cn(budgetBtn, "bg-cyan-600/20 text-cyan-300 ring-cyan-500/40")}
        >
          Salvar
        </button>
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-400">
          <span>
            Início: <span className="text-slate-200">{formatIsoDateBr(task.early_start)}</span>
          </span>
          <span>
            Fim: <span className="text-slate-200">{formatIsoDateBr(task.early_finish)}</span>
          </span>
          <span>
            Folga:{" "}
            <span className={task.is_critical ? "text-red-400" : "text-emerald-400"}>
              {task.total_float_days ?? "—"}d
            </span>
          </span>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <LinkSection
          title="Predecessoras"
          hint="Atividades que devem terminar/iniciar antes desta"
          candidates={predCandidates}
          draft={predDraft}
          linkType={predLinkType}
          lag={predLag}
          links={predecessorLinks}
          otherEnd="predecessor"
          currentCode={task.budget_code}
          taskLabel={taskLabel}
          busy={busy}
          onDraftChange={onPredChange}
          onLinkTypeChange={onPredLinkTypeChange}
          onLagChange={onPredLagChange}
          onAdd={onAddPredecessor}
          onRemove={onRemoveLink}
        />

        <LinkSection
          title="Sucessoras"
          hint="Atividades que dependem desta"
          candidates={succCandidates}
          draft={succDraft}
          linkType={succLinkType}
          lag={succLag}
          links={successorLinks}
          otherEnd="successor"
          currentCode={task.budget_code}
          taskLabel={taskLabel}
          busy={busy}
          onDraftChange={onSuccChange}
          onLinkTypeChange={onSuccLinkTypeChange}
          onLagChange={onSuccLagChange}
          onAdd={onAddSuccessor}
          onRemove={onRemoveLink}
        />
      </div>
    </div>
  );
}

function LinkSection({
  title,
  hint,
  candidates,
  draft,
  linkType,
  lag,
  links,
  otherEnd,
  currentCode,
  taskLabel,
  busy,
  onDraftChange,
  onLinkTypeChange,
  onLagChange,
  onAdd,
  onRemove,
}: {
  title: string;
  hint: string;
  candidates: ScheduleTask[];
  draft: string;
  linkType: LinkType;
  lag: string;
  links: ScheduleLink[];
  otherEnd: "predecessor" | "successor";
  currentCode: string;
  taskLabel: (id: string) => string;
  busy: boolean;
  onDraftChange: (v: string) => void;
  onLinkTypeChange: (v: LinkType) => void;
  onLagChange: (v: string) => void;
  onAdd: () => void;
  onRemove: (linkId: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div>
        <h4 className="text-[11px] font-medium uppercase tracking-wider text-violet-400">{title}</h4>
        <p className="text-[10px] text-slate-500">{hint}</p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className={cn(budgetField, "min-w-[180px] max-w-[280px] flex-1")}>
          <span className={budgetFieldLabel}>Atividade</span>
          <select
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            className={budgetInput}
          >
            <option value="">Selecione…</option>
            {candidates.map((t) => (
              <option key={t.task_id} value={t.task_id}>
                {t.budget_code} — {t.name.slice(0, 36)}
              </option>
            ))}
          </select>
        </label>

        <label className={cn(budgetField, "w-[72px]")}>
          <span className={budgetFieldLabel}>Tipo</span>
          <select
            value={linkType}
            onChange={(e) => onLinkTypeChange(e.target.value as LinkType)}
            className={budgetInput}
            title="FS= Fim-Início · SS= Início-Início · FF= Fim-Fim · SF= Início-Fim"
          >
            {LINK_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        <label className={cn(budgetField, "w-[72px]")}>
          <span className={budgetFieldLabel}>Lag (d)</span>
          <input
            type="number"
            min={0}
            max={365}
            value={lag}
            onChange={(e) => onLagChange(e.target.value)}
            className={budgetInput}
          />
        </label>

        <button
          type="button"
          disabled={busy || !draft}
          onClick={onAdd}
          className={cn(budgetBtn, "bg-violet-600/20 text-violet-300 ring-violet-500/40")}
        >
          Adicionar
        </button>
      </div>

      {links.length === 0 ? (
        <p className="text-[9px] text-slate-600">Nenhum vínculo.</p>
      ) : (
        <ul className="max-h-20 space-y-0.5 overflow-y-auto text-[10px]">
          {links.map((link) => {
            const otherId = otherEnd === "predecessor" ? link.predecessor_id : link.successor_id;
            const arrow =
              otherEnd === "predecessor"
                ? `${taskLabel(otherId)} → ${currentCode}`
                : `${currentCode} → ${taskLabel(otherId)}`;
            return (
              <li
                key={link.link_id}
                className="flex items-center justify-between gap-2 rounded bg-slate-900/60 px-2 py-1.5 text-slate-400"
              >
                <span className="min-w-0 truncate" title={arrow}>
                  {arrow}{" "}
                  <span className="text-slate-600">
                    ({link.link_type}
                    {link.lag_days ? ` +${link.lag_days}d` : ""})
                  </span>
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onRemove(link.link_id)}
                  className="shrink-0 rounded px-1.5 py-0.5 text-[10px] text-red-400 ring-1 ring-red-500/30 hover:bg-red-500/10"
                >
                  Remover
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
