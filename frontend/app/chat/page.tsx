"use client";

import { useCallback, useState } from "react";
import ChatBox from "@/components/ChatBox";
import MessageList from "@/components/MessageList";
import { api } from "@/services/api";
import type { ChatMessage } from "@/types/api";
import { generateId } from "@/lib/utils";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSend = useCallback(
    async (text: string, options: { useRag: boolean; persist: boolean }) => {
      const userMessage: ChatMessage = {
        id: generateId(),
        role: "user",
        content: text,
      };

      setMessages((prev) => [...prev, userMessage]);
      setLoading(true);
      setError(null);

      try {
        const response = await api.chat({
          text,
          use_rag: options.useRag,
          persist: options.persist,
        });

        const assistantMessage: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: response.result || response.response || "Sem resposta do agente.",
          meta: {
            discipline: response.discipline || response.route?.discipline,
            agent: response.agent || response.route?.agent,
            extra: response.extra,
            raw: response,
          },
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Erro ao comunicar com a API";
        setError(message);
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "assistant",
            content: `Erro: ${message}. Verifique se o backend está rodando em http://localhost:8000`,
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return (
    <>
      <header className="shrink-0 border-b border-slate-800/80 px-6 py-4">
        <h1 className="text-lg font-semibold text-white">Chat IA</h1>
        <p className="text-sm text-slate-500">
          Router → RAG v2 → Agente especializado
        </p>
      </header>

      {error && (
        <div className="mx-6 mt-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
          {error}
        </div>
      )}

      <MessageList messages={messages} loading={loading} />
      <ChatBox onSend={handleSend} loading={loading} />
    </>
  );
}
