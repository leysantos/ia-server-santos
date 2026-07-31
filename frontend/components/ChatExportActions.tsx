"use client";

import { useEffect, useMemo, useState } from "react";
import type { ChatMessage } from "@/types/api";
import {
  downloadChatCroqui,
  downloadChatExport,
  fetchChatDocumentSuggestions,
  type ChatDocSuggestion,
  type ChatExportKind,
} from "@/services/api";

function findSourceQuestion(messages: ChatMessage[], assistantId: string): string | undefined {
  const idx = messages.findIndex((m) => m.id === assistantId);
  if (idx <= 0) return undefined;
  for (let i = idx - 1; i >= 0; i -= 1) {
    if (messages[i].role === "user" && messages[i].content?.trim()) {
      return messages[i].content.trim();
    }
  }
  return undefined;
}

const FALLBACK_TITLES: Record<ChatExportKind, string> = {
  memoria: "Memória de Cálculo",
  trd: "Termo de Referência Descritivo (TRD)",
  memorial: "Memorial Descritivo",
  parecer: "Parecer Técnico",
  especificacao: "Especificação Técnica",
  checklist: "Checklist de Verificação Técnica",
  nota_orcamento: "Nota Técnica de Orçamento",
  resposta: "Resposta Técnica — Chat IA",
};

type BusyKey = string | null;

interface ChatExportActionsProps {
  message: ChatMessage;
  messages: ChatMessage[];
}

export default function ChatExportActions({ message, messages }: ChatExportActionsProps) {
  const [busy, setBusy] = useState<BusyKey>(null);
  const [error, setError] = useState<string | null>(null);
  const [croquiUrl, setCroquiUrl] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<ChatDocSuggestion[] | null>(null);

  const sourceQuestion = useMemo(
    () => findSourceQuestion(messages, message.id),
    [messages, message.id]
  );

  const discipline =
    message.meta?.discipline || message.meta?.raw?.discipline || undefined;
  const routeMode = String(message.meta?.raw?.route?.mode || "") || undefined;
  const eligible =
    message.role === "assistant" &&
    !message.meta?.streaming &&
    (message.content || "").trim().length >= 280;

  useEffect(() => {
    if (!eligible) {
      setSuggestions(null);
      return;
    }
    let cancelled = false;
    setSuggestions(null);
    fetchChatDocumentSuggestions({
      text: message.content,
      discipline,
      source_question: sourceQuestion,
      route_mode: routeMode,
    })
      .then((items) => {
        if (!cancelled) setSuggestions(items);
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [eligible, message.content, discipline, sourceQuestion, routeMode]);

  if (!eligible || suggestions === null) return null;
  if (suggestions.length === 0) return null;

  const runExport = async (kind: ChatExportKind, format: "pdf" | "docx", label: string) => {
    const key = `${kind}-${format}`;
    setBusy(key);
    setError(null);
    try {
      await downloadChatExport({
        text: message.content,
        kind,
        format,
        discipline,
        source_question: sourceQuestion,
        title: FALLBACK_TITLES[kind] || label,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const runCroqui = async () => {
    setBusy("croqui");
    setError(null);
    try {
      const blob = await downloadChatCroqui({
        text: message.content,
        source_question: sourceQuestion,
        llm_model: message.meta?.llmModel,
      });
      if (croquiUrl) URL.revokeObjectURL(croquiUrl);
      const url = URL.createObjectURL(blob);
      setCroquiUrl(url);
      const a = document.createElement("a");
      a.href = url;
      a.download = "croqui_chat.png";
      a.click();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const btn =
    "inline-flex h-7 w-[6.75rem] shrink-0 items-center justify-center rounded-lg border border-white/10 bg-slate-800/80 px-2 text-[11px] font-medium text-slate-200 transition hover:border-brand-500/40 hover:bg-slate-700/90 disabled:cursor-wait disabled:opacity-60";

  return (
    <div className="mt-3 border-t border-white/5 pt-3">
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
        Documentos sugeridos para esta resposta
      </p>
      <p className="mb-2 text-[10px] text-slate-600">
        As opções mudam conforme o conteúdo (cálculo, parecer, orçamento, PCI…).
      </p>
      <div className="flex flex-col gap-2">
        {suggestions.map((s) => (
          <div key={s.kind} className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 min-w-[9.5rem] text-[11px] text-slate-400" title={s.reason}>
              {s.label}
            </span>
            {s.kind === "croqui" ? (
              <button type="button" className={btn} disabled={!!busy} onClick={runCroqui}>
                {busy === "croqui" ? "Gerando…" : "Baixar croqui"}
              </button>
            ) : (
              <>
                {s.formats.includes("pdf") && (
                  <button
                    type="button"
                    className={btn}
                    disabled={!!busy}
                    onClick={() => runExport(s.kind as ChatExportKind, "pdf", s.label)}
                  >
                    {busy === `${s.kind}-pdf` ? "Gerando…" : "PDF"}
                  </button>
                )}
                {s.formats.includes("docx") && (
                  <button
                    type="button"
                    className={btn}
                    disabled={!!busy}
                    onClick={() => runExport(s.kind as ChatExportKind, "docx", s.label)}
                  >
                    {busy === `${s.kind}-docx` ? "Gerando…" : "Word"}
                  </button>
                )}
              </>
            )}
          </div>
        ))}
      </div>
      {error && <p className="mt-2 text-[11px] text-rose-300">{error}</p>}
      {croquiUrl && (
        <div className="mt-3 overflow-hidden rounded-lg border border-white/10 bg-black/20">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={croquiUrl} alt="Croqui gerado" className="max-h-72 w-full object-contain" />
          <div className="flex justify-end gap-2 border-t border-white/5 px-2 py-1.5">
            <a
              href={croquiUrl}
              download="croqui_chat.png"
              className="text-[11px] text-brand-300 hover:underline"
            >
              Baixar novamente
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
