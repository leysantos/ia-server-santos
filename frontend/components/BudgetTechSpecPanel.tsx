"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, techSpecComposeStream } from "@/services/api";
import type { BudgetSessionResponse, TechSpecDocument, TechSpecFormatting } from "@/types/api";
import { cn } from "@/lib/utils";
import { extractBodyHtml, markdownToHtml } from "@/lib/markdown-lite";
import { budgetBtn, budgetField, budgetFieldLabel, budgetTextarea } from "@/lib/budget-ui";
import ModelSelector from "@/components/ModelSelector";
import { useLlmModelSelection } from "@/hooks/useLlmModel";

const DEFAULT_FORMATTING: TechSpecFormatting = {
  font_family: "Calibri",
  font_size: 11,
  line_spacing: 1.15,
  margin_cm: 2.5,
  page_numbers: false,
  logo_text: null,
  document_title: null,
};

const PROMPT_EXAMPLES = [
  'Adicione o título "Especificação Técnica — Obra XYZ"',
  "Adicione numeração de páginas no rodapé",
  "Adicione a logo (Construtora Santos)",
  "Detalhe materiais e métodos da etapa de fundações",
];

interface BudgetTechSpecPanelProps {
  session: BudgetSessionResponse;
  loading?: boolean;
  onUpdate: (session: BudgetSessionResponse) => void;
  onError?: (err: unknown, title?: string) => void;
}

type LogEntry = { id: number; message: string; phase?: string };

export default function BudgetTechSpecPanel({
  session,
  loading,
  onUpdate,
  onError,
}: BudgetTechSpecPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [composing, setComposing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [streamPreview, setStreamPreview] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [formatting, setFormatting] = useState<TechSpecFormatting>(DEFAULT_FORMATTING);
  const [tokenCount, setTokenCount] = useState(0);
  const logEndRef = useRef<HTMLDivElement>(null);
  const previewRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const logIdRef = useRef(0);
  const streamMdRef = useRef("");
  const { model: llmModel, setModel: setLlmModel } = useLlmModelSelection();

  const spec = session.tech_spec;
  const hasDocument = Boolean(bodyHtml || markdown || spec?.markdown);

  useEffect(() => {
    if (spec) {
      setMarkdown(spec.markdown || "");
      const body = spec.html_content || markdownToHtml(spec.markdown || "");
      setBodyHtml(body.includes("tech-spec-body") ? extractBodyHtml(body) : body);
      setFormatting({ ...DEFAULT_FORMATTING, ...(spec.formatting || {}) });
    }
  }, [session.session_id, spec?.updated_at]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, streamPreview, tokenCount]);

  const syncBodyHtml = useCallback((html: string) => {
    if (previewRef.current) {
      previewRef.current.innerHTML =
        html || "<p><em>Corpo do documento…</em></p>";
    }
  }, []);

  useEffect(() => {
    if (!composing && previewRef.current) {
      syncBodyHtml(bodyHtml);
    }
  }, [bodyHtml, composing, session.session_id, syncBodyHtml]);

  const pushLog = useCallback((message: string, phase?: string) => {
    logIdRef.current += 1;
    setLogs((prev) => [...prev.slice(-120), { id: logIdRef.current, message, phase }]);
  }, []);

  const applyStreamPayload = useCallback(
    (data: Record<string, unknown>, fromToken = false) => {
      if (data.formatting && typeof data.formatting === "object") {
        setFormatting((f) => ({ ...f, ...(data.formatting as TechSpecFormatting) }));
      }
      const md = typeof data.markdown === "string" ? data.markdown : null;
      const fullHtml = typeof data.html_content === "string" ? data.html_content : null;

      if (md !== null) {
        streamMdRef.current = md;
        setStreamPreview(md);
        setMarkdown(md);
      }

      if (fullHtml) {
        const body = extractBodyHtml(fullHtml);
        setBodyHtml(body);
        if (fromToken || composing) syncBodyHtml(body);
      } else if (md !== null) {
        const body = markdownToHtml(md);
        setBodyHtml(body);
        if (fromToken || composing) syncBodyHtml(body);
      }
    },
    [composing, syncBodyHtml]
  );

  const runStream = async (mode: "generate" | "edit") => {
    if (composing) return;
    if (mode === "edit" && !prompt.trim()) {
      onError?.(new Error("Descreva a alteração no prompt."), "Prompt obrigatório");
      return;
    }

    setComposing(true);
    setLogs([]);
    setStreamPreview("");
    setTokenCount(0);
    if (mode === "generate") streamMdRef.current = "";
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    pushLog(
      mode === "edit"
        ? "Aplicando edição via IA no documento…"
        : "Iniciando geração da especificação técnica…",
      "start"
    );

    try {
      for await (const event of techSpecComposeStream(
        session.session_id,
        {
          prompt: prompt.trim() || undefined,
          mode,
          use_llm: true,
          llm_model: llmModel !== "auto" ? llmModel : undefined,
        },
        abortRef.current.signal
      )) {
        const data = event.data || {};
        switch (event.type) {
          case "status":
            pushLog(String(data.message || "Processando…"), String(data.phase || "status"));
            break;
          case "log":
            pushLog(String(data.message || ""), String(data.phase || "log"));
            break;
          case "token": {
            const t = String(data.token || "");
            setTokenCount((n) => n + 1);
            streamMdRef.current += t;
            applyStreamPayload(
              {
                markdown: streamMdRef.current,
                html_content: undefined,
                formatting,
              },
              true
            );
            syncBodyHtml(markdownToHtml(streamMdRef.current));
            break;
          }
          case "preview":
            applyStreamPayload(data, true);
            break;
          case "done": {
            const updated = data.session as BudgetSessionResponse | undefined;
            const ts = data.tech_spec as TechSpecDocument | undefined;
            if (ts) {
              setMarkdown(ts.markdown);
              setFormatting({ ...DEFAULT_FORMATTING, ...(ts.formatting || {}) });
              const body =
                ts.html_content && ts.html_content.includes("tech-spec-body")
                  ? extractBodyHtml(ts.html_content)
                  : ts.html_content || markdownToHtml(ts.markdown);
              setBodyHtml(body);
              syncBodyHtml(body);
            }
            pushLog(String(data.summary || "Concluído."), "done");
            if (updated) onUpdate(updated);
            break;
          }
          case "error":
            throw new Error(String(data.message || "Erro na operação"));
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError?.(err, mode === "edit" ? "Erro ao editar especificação" : "Erro ao gerar especificação");
        pushLog(err instanceof Error ? err.message : String(err), "error");
      }
    } finally {
      setComposing(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const html = previewRef.current?.innerHTML ?? bodyHtml;
      const result = await api.pricingUpdateTechSpec(session.session_id, {
        markdown,
        html_content: html,
        formatting,
        title:
          formatting.document_title ||
          spec?.title ||
          `Especificação Técnica — ${session.title}`,
      });
      setBodyHtml(result.tech_spec.html_content || html);
      syncBodyHtml(result.tech_spec.html_content || html);
      if (result.tech_spec.formatting) {
        setFormatting({ ...DEFAULT_FORMATTING, ...result.tech_spec.formatting });
      }
      onUpdate(result.session);
      pushLog("Alterações salvas na sessão.", "save");
    } catch (err) {
      onError?.(err, "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  const execCmd = (command: string, value?: string) => {
    previewRef.current?.focus();
    document.execCommand(command, false, value);
    if (previewRef.current) setBodyHtml(previewRef.current.innerHTML);
  };

  const adjustFontSize = (delta: number) => {
    setFormatting((f) => ({
      ...f,
      font_size: Math.min(18, Math.max(9, f.font_size + delta)),
    }));
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 lg:flex-row">
      <div className="flex min-h-0 w-full shrink-0 flex-col rounded-xl bg-slate-900/50 ring-1 ring-slate-700/50 lg:w-[38%]">
        <div className="border-b border-slate-700/50 px-3 py-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-violet-300">
            Agente — Especificação Técnica
          </h3>
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-2 p-3">
          <label className={budgetField}>
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className={budgetFieldLabel}>
                {hasDocument ? "Prompt de edição" : "Instruções (opcional)"}
              </span>
              <ModelSelector
                id="tech-spec-model"
                value={llmModel}
                onChange={setLlmModel}
                className="shrink-0"
              />
            </div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={4}
              placeholder={
                hasDocument
                  ? 'Ex.: "Adicione o título ESPECIFICAÇÃO TÉCNICA", "Adicione numeração de páginas", "Adicione a logo (Empresa X)", "Detalhe a etapa 2…"'
                  : "Ex.: detalhar materiais da etapa fundações, citar NBR 6118…"
              }
              className={cn(budgetTextarea, "min-h-[88px] resize-none text-sm")}
              disabled={composing}
            />
          </label>

          <div className="flex flex-wrap gap-1">
            {PROMPT_EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                disabled={composing}
                onClick={() => setPrompt(ex)}
                className="rounded-full bg-slate-800/80 px-2 py-0.5 text-[10px] text-slate-400 ring-1 ring-slate-700 hover:text-violet-200"
              >
                {ex.length > 42 ? `${ex.slice(0, 42)}…` : ex}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading || composing}
              onClick={() => runStream("generate")}
              className={cn(
                budgetBtn,
                "bg-violet-600/30 text-violet-100 ring-violet-500/40 hover:bg-violet-600/45"
              )}
            >
              {composing ? "Processando…" : "Gerar do orçamento"}
            </button>
            <button
              type="button"
              disabled={loading || composing || !hasDocument}
              onClick={() => runStream("edit")}
              className={cn(
                budgetBtn,
                "bg-amber-600/25 text-amber-100 ring-amber-500/35 hover:bg-amber-600/40"
              )}
              title={hasDocument ? undefined : "Gere o documento primeiro"}
            >
              Editar com IA
            </button>
            <button
              type="button"
              disabled={loading || saving || composing || !hasDocument}
              onClick={handleSave}
              className={cn(budgetBtn, "bg-cyan-600/20 text-cyan-200 ring-cyan-500/30")}
            >
              {saving ? "Salvando…" : "Salvar"}
            </button>
          </div>

          <div className="min-h-0 flex-1 rounded-lg bg-slate-950/80 ring-1 ring-slate-800">
            <div className="border-b border-slate-800 px-2 py-1 text-[10px] font-medium uppercase text-slate-500">
              Execução em tempo real
              {composing && <span className="ml-2 text-violet-400">{tokenCount} tokens</span>}
            </div>
            <div className="max-h-48 overflow-y-auto p-2 font-mono text-[11px] leading-relaxed lg:max-h-none lg:flex-1">
              {logs.length === 0 && !composing && (
                <p className="text-slate-600">
                  Gere o documento a partir do orçamento ou use <strong>Editar com IA</strong> para
                  título, logo, numeração de páginas e alterações de conteúdo — tudo visível no
                  preview ao vivo.
                </p>
              )}
              {logs.map((entry) => (
                <p
                  key={entry.id}
                  className={cn(
                    "mb-1",
                    entry.phase === "error" && "text-red-400",
                    entry.phase === "done" && "text-emerald-400",
                    entry.phase === "format" && "text-amber-300",
                    entry.phase === "llm" && "text-violet-300",
                    !entry.phase?.match(/error|done|format|llm/) && "text-slate-400"
                  )}
                >
                  › {entry.message}
                </p>
              ))}
              {composing && streamPreview && (
                <p className="mt-2 whitespace-pre-wrap border-t border-slate-800 pt-2 text-slate-500">
                  {streamPreview.slice(-500)}
                </p>
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col rounded-xl bg-slate-900/50 ring-1 ring-slate-700/50">
        <div className="flex flex-wrap items-center gap-1 border-b border-slate-700/50 px-2 py-1.5">
          <FormatBtn label="B" title="Negrito" onClick={() => execCmd("bold")} />
          <FormatBtn label="I" title="Itálico" onClick={() => execCmd("italic")} className="italic" />
          <FormatBtn label="U" title="Sublinhado" onClick={() => execCmd("underline")} className="underline" />
          <span className="mx-1 h-4 w-px bg-slate-700" />
          <FormatBtn label="H1" onClick={() => execCmd("formatBlock", "h1")} />
          <FormatBtn label="H2" onClick={() => execCmd("formatBlock", "h2")} />
          <FormatBtn label="H3" onClick={() => execCmd("formatBlock", "h3")} />
          <span className="mx-1 h-4 w-px bg-slate-700" />
          <FormatBtn label="≡" title="Lista" onClick={() => execCmd("insertUnorderedList")} />
          <FormatBtn label="↔" title="Justificar" onClick={() => execCmd("justifyFull")} />
          <FormatBtn label="▣" title="Centralizar" onClick={() => execCmd("justifyCenter")} />
          <span className="mx-1 h-4 w-px bg-slate-700" />
          <FormatBtn label="A−" onClick={() => adjustFontSize(-1)} />
          <span className="px-1 text-[10px] text-slate-500">{formatting.font_size}pt</span>
          <FormatBtn label="A+" onClick={() => adjustFontSize(1)} />
          <button
            type="button"
            disabled={!hasDocument}
            onClick={async () => {
              try {
                await handleSave();
                window.open(api.pricingExportTechSpecUrl(session.session_id), "_blank");
              } catch (err) {
                onError?.(err, "Erro ao exportar Word");
              }
            }}
            className={cn(budgetBtn, "ml-auto bg-emerald-600/25 text-emerald-200 ring-emerald-500/35")}
          >
            Exportar Word
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto bg-slate-800/40 p-4">
          <div
            className={cn(
              "relative mx-auto min-h-[70vh] max-w-[210mm] bg-white shadow-lg ring-1 ring-slate-300/80",
              composing && "ring-2 ring-violet-400/50"
            )}
            style={{
              padding: `${formatting.margin_cm}cm`,
              fontFamily: formatting.font_family,
              fontSize: `${formatting.font_size}pt`,
              lineHeight: formatting.line_spacing,
            }}
          >
            {formatting.logo_text && (
              <div className="mb-4 border border-dashed border-slate-400 bg-slate-50 py-3 text-center text-sm font-semibold text-slate-600">
                [LOGO: {formatting.logo_text}]
              </div>
            )}
            {formatting.document_title && (
              <h1 className="mb-5 text-center text-2xl font-bold text-slate-900">
                {formatting.document_title}
              </h1>
            )}
            <div
              ref={previewRef}
              contentEditable={!composing}
              suppressContentEditableWarning
              className="tech-spec-preview min-h-[50vh] text-slate-900 outline-none [&_h1]:mb-3 [&_h1]:text-2xl [&_h1]:font-bold [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:text-lg [&_h3]:font-semibold [&_li]:ml-4 [&_p]:mb-2 [&_ul]:list-disc [&_ul]:pl-5"
              onInput={() => {
                if (previewRef.current) setBodyHtml(previewRef.current.innerHTML);
              }}
            />
            {formatting.page_numbers && (
              <div className="mt-6 border-t border-slate-300 pt-2 text-center text-[9pt] text-slate-500">
                Página 1
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FormatBtn({
  label,
  title,
  onClick,
  className,
}: {
  label: string;
  title?: string;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      title={title || label}
      onClick={onClick}
      className={cn(
        "rounded px-2 py-0.5 text-xs text-slate-300 ring-1 ring-slate-700 hover:bg-slate-800 hover:text-white",
        className
      )}
    >
      {label}
    </button>
  );
}
