"use client";

import { FormEvent, KeyboardEvent, useState } from "react";

interface ChatBoxProps {
  onSend: (text: string, options: { useRag: boolean; persist: boolean }) => void;
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

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    onSend(trimmed, { useRag, persist });
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
    <form
      onSubmit={handleSubmit}
      className="border-t border-slate-800/80 bg-slate-950/90 p-4 backdrop-blur-xl"
    >
      <div className="mx-auto max-w-4xl">
        <div className="mb-3 flex flex-wrap items-center gap-4 text-xs text-slate-400">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={useRag}
              onChange={(e) => setUseRag(e.target.checked)}
              className="rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500/50"
            />
            RAG v2 (normas NBR)
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={persist}
              onChange={(e) => setPersist(e.target.checked)}
              className="rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500/50"
            />
            Salvar no histórico
          </label>
        </div>

        <div className="flex items-end gap-3 rounded-2xl bg-slate-900/90 p-2 ring-1 ring-slate-700/80 focus-within:ring-cyan-500/40">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            disabled={loading}
            className="max-h-40 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-white placeholder:text-slate-500 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan-600 text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            ) : (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-slate-600">
          Enter para enviar · Shift+Enter para nova linha
        </p>
      </div>
    </form>
  );
}
