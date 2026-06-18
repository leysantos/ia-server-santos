"use client";

import type { ChatMessage } from "@/types/api";
import JsonViewer from "./JsonViewer";
import LoadingSpinner from "./LoadingSpinner";

interface MessageListProps {
  messages: ChatMessage[];
  loading?: boolean;
}

export default function MessageList({ messages, loading }: MessageListProps) {
  if (messages.length === 0 && !loading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-800/80 ring-1 ring-slate-700">
          <svg className="h-8 w-8 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-white">Como posso ajudar na engenharia?</h2>
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
              className="rounded-full bg-slate-800/80 px-3 py-1.5 text-xs text-slate-400 ring-1 ring-slate-700"
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
                ? "bg-cyan-600 text-white shadow-lg shadow-cyan-600/20"
                : "bg-slate-800/90 text-slate-100 ring-1 ring-slate-700/80"
            }`}
          >
            {message.role === "assistant" && message.meta?.discipline && (
              <div className="mb-2 flex flex-wrap gap-2">
                <span className="rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-xs font-medium text-cyan-300 ring-1 ring-cyan-500/30">
                  {message.meta.discipline}
                </span>
                {message.meta.agent && (
                  <span className="rounded-full bg-slate-700/80 px-2.5 py-0.5 text-xs text-slate-400">
                    {message.meta.agent}
                  </span>
                )}
              </div>
            )}
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
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

      {loading && (
        <div className="flex justify-start">
          <div className="rounded-2xl bg-slate-800/90 px-4 py-3 ring-1 ring-slate-700/80">
            <LoadingSpinner label="Agente analisando..." />
          </div>
        </div>
      )}
    </div>
  );
}
