"use client";

import { FormEvent, KeyboardEvent, useId, useState } from "react";
import { ShellFooter } from "@/components/ShellHeader";
import ModelSelector from "@/components/ModelSelector";
import { useLlmModelSelection } from "@/hooks/useLlmModel";

export interface ChatSendOptions {
  useRag: boolean;
  persist: boolean;
  llmModel: string;
}

interface ChatBoxProps {
  onSend: (text: string, options: ChatSendOptions) => void;
  loading?: boolean;
  placeholder?: string;
}

export default function ChatBox({
  onSend,
  loading = false,
  placeholder = "Descreva seu problema de engenharia...",
}: ChatBoxProps) {
  const [text, setText] = useState("");
  const [useRag, setUseRag] = useState(true);
  const [persist, setPersist] = useState(true);
  const { model, setModel } = useLlmModelSelection();
  const modelSelectId = useId();

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    onSend(trimmed, { useRag, persist, llmModel: model });
    setText("");
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <ShellFooter className="bg-surface/90 backdrop-blur-xl" innerClassName="items-start">
      <form onSubmit={handleSubmit} className="mx-auto w-full max-w-4xl">
        <div className="flex w-full flex-col gap-3.5">
          <div className="flex min-h-[1.75rem] flex-wrap items-center justify-center gap-x-6 gap-y-2 sm:justify-start">
            <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
                className="rounded border-white/10 bg-surface-card text-brand-500 focus:ring-brand-500/50"
              />
              RAG v2 (normas NBR)
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={persist}
                onChange={(e) => setPersist(e.target.checked)}
                className="rounded border-white/10 bg-surface-card text-brand-500 focus:ring-brand-500/50"
              />
              Salvar no histórico
            </label>
            <p className="hidden flex-1 text-center text-xs text-slate-600 sm:block sm:text-right">
              Enter envia · Shift+Enter nova linha
            </p>
          </div>

          <ModelSelector
            id={modelSelectId}
            value={model}
            onChange={setModel}
            className="px-1"
          />

          <div className="flex items-center gap-3 rounded-2xl border border-white/5 bg-surface-card p-2 focus-within:border-brand-500/40 focus-within:ring-1 focus-within:ring-brand-500/30">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={1}
              disabled={loading}
              className="max-h-40 min-h-[2.75rem] flex-1 resize-none bg-transparent px-3 py-2.5 text-sm leading-relaxed text-white placeholder:text-slate-500 focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !text.trim()}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white shadow-brand-sm transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Enviar mensagem"
            >
              {loading ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              ) : (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              )}
            </button>
          </div>

          <p className="text-center text-xs text-slate-600 sm:hidden">
            Enter envia · Shift+Enter nova linha
          </p>
        </div>
      </form>
    </ShellFooter>
  );
}
