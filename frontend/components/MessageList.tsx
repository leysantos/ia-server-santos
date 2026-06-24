"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/types/api";
import JsonViewer from "./JsonViewer";
import LoadingSpinner from "./LoadingSpinner";

interface MessageListProps {
  messages: ChatMessage[];
  loading?: boolean;
}

export default function MessageList({ messages, loading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isStreaming = messages.some((m) => m.meta?.streaming);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: isStreaming ? "auto" : "smooth",
      block: "end",
    });
  }, [messages, isStreaming]);

  if (messages.length === 0 && !loading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/5 bg-surface-card shadow-glow">
          <svg className="h-8 w-8 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <h2 className="gradient-text text-xl font-semibold">Como posso ajudar na engenharia?</h2>
        <p className="mt-2 max-w-md text-sm text-slate-400">
          Descreva um problema técnico — estruturas, hidráulica, elétrica, orçamento e mais.
          O router identifica a disciplina e o agente especializado responde.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {[
            "Dimensionar viga de concreto armado",
            "Projeto hidráulico predial NBR 5626",
            "Orçamento estimativo de edificação",
          ].map((hint) => (
            <span
              key={hint}
              className="rounded-full border border-white/5 bg-surface-card px-3 py-1.5 text-xs text-slate-400"
            >
              {hint}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6 md:px-8">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-3xl rounded-2xl px-4 py-3 ${
              message.role === "user"
                ? "bg-brand-600 text-white shadow-brand-sm"
                : "border border-white/5 bg-surface-card text-slate-100"
            }`}
          >
            {message.role === "assistant" && (message.meta?.discipline || message.meta?.streamStatus) && (
              <div className="mb-2 flex flex-col gap-2">
                <div className="flex flex-wrap gap-2">
                  {message.meta?.discipline && (
                    <span className="rounded-full bg-brand-500/15 px-2.5 py-0.5 text-xs font-medium text-brand-300 ring-1 ring-brand-500/30">
                      {message.meta.discipline}
                    </span>
                  )}
                  {message.meta?.agent && (
                    <span className="rounded-full bg-slate-700/80 px-2.5 py-0.5 text-xs text-slate-400">
                      {message.meta.agent}
                    </span>
                  )}
                  {message.meta?.llmModel && (
                    <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-300 ring-1 ring-emerald-500/20">
                      {message.meta.llmModel}
                    </span>
                  )}
                  {message.meta?.streaming && (
                    <span className="rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs text-amber-300 ring-1 ring-amber-500/20">
                      ao vivo
                    </span>
                  )}
                </div>
                {message.meta?.streamStatus && (
                  <p className="text-xs text-slate-500">{message.meta.streamStatus}</p>
                )}
              </div>
            )}
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {message.content}
              {message.meta?.streaming && (
                <span className="streaming-cursor ml-0.5 inline-block text-cyan-400">
                  ▍
                </span>
              )}
            </p>
            {message.meta?.extra && (
              <details className="mt-3">
                <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-300">
                  Ver detalhes técnicos
                </summary>
                <JsonViewer data={message.meta.extra} className="mt-2" />
              </details>
            )}
          </div>
        </div>
      ))}

      {loading && messages.every((m) => !m.meta?.streaming) && (
        <div className="flex justify-start">
          <div className="rounded-2xl bg-slate-800/90 px-4 py-3 ring-1 ring-slate-700/80">
            <LoadingSpinner label="Agente analisando..." />
          </div>
        </div>
      )}

      <div ref={bottomRef} aria-hidden className="h-px shrink-0" />
    </div>
  );
}
