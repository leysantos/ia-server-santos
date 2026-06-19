"use client";

import { useCallback, useEffect, useState } from "react";
import ChatBox from "@/components/ChatBox";
import MessageList from "@/components/MessageList";
import { chatStream, api } from "@/services/api";
import type { ChatMessage, ChatResponse } from "@/types/api";
import { generateId } from "@/lib/utils";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [configuredModels, setConfiguredModels] = useState<string | null>(null);

  useEffect(() => {
    api.health().then((health) => {
      if (health.models?.installed_llm) {
        setConfiguredModels(`WSL: ${health.models.installed_llm}`);
      } else if (health.installed_models?.length) {
        const llms = health.installed_models.filter(
          (m) => !m.toLowerCase().includes("embed")
        );
        setConfiguredModels(
          `WSL: ${llms.map((m) => m.replace(/:latest$/, "")).join(" · ")}`
        );
      } else if (health.models) {
        setConfiguredModels(
          `chat: ${health.models.chat} · eng: ${health.models.engineering}`
        );
      }
    }).catch(() => {});
  }, []);

  const updateAssistant = useCallback(
    (id: string, patch: Partial<ChatMessage>) => {
      setMessages((prev) =>
        prev.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg))
      );
    },
    []
  );

  const handleSend = useCallback(
    async (text: string, options: { useRag: boolean; persist: boolean }) => {
      const userMessage: ChatMessage = {
        id: generateId(),
        role: "user",
        content: text,
      };

      const assistantId = generateId();
      const assistantPlaceholder: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        meta: {
          streaming: true,
          streamStatus: "Analisando intenção...",
        },
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      setLoading(true);
      setError(null);

      try {
        let accumulated = "";
        let finalResponse: ChatResponse | null = null;

        for await (const event of chatStream({
          text,
          use_rag: options.useRag,
          persist: options.persist,
        })) {
          if (event.type === "status") {
            const message = String(event.data.message ?? "Processando...");
            const model = event.data.llm_model ? String(event.data.llm_model) : undefined;
            if (model) setActiveModel(model);
            updateAssistant(assistantId, {
              meta: {
                streaming: true,
                streamStatus: message,
                llmModel: model,
                discipline: event.data.step
                  ? String((event.data.step as { discipline?: string }).discipline ?? "")
                  : undefined,
                agent: event.data.step
                  ? String((event.data.step as { agent?: string }).agent ?? "")
                  : undefined,
              },
            });
          }

          if (event.type === "token") {
            const token = String(event.data.token ?? "");
            const model = event.data.llm_model ? String(event.data.llm_model) : undefined;
            if (model) setActiveModel(model);
            if (token && !event.data.meta) {
              accumulated += token;
            } else if (token) {
              accumulated += token;
            }
            updateAssistant(assistantId, {
              content: accumulated,
              meta: {
                streaming: true,
                streamStatus: `Gerando: ${event.data.agent ?? "agente"}...`,
                llmModel: model,
                discipline: String(event.data.discipline ?? ""),
                agent: String(event.data.agent ?? ""),
              },
            });
          }

          if (event.type === "done") {
            finalResponse = event.data as unknown as ChatResponse;
            accumulated = finalResponse.result || accumulated;
          }
        }

        const finalModel =
          (finalResponse?.extra?.llm_model as string | undefined) ||
          (finalResponse?.extra?.model as string | undefined);

        if (finalModel) setActiveModel(finalModel);

        updateAssistant(assistantId, {
          content:
            accumulated ||
            finalResponse?.result ||
            finalResponse?.response ||
            "Sem resposta do agente.",
          meta: {
            streaming: false,
            streamStatus: undefined,
            llmModel: finalModel,
            discipline:
              finalResponse?.discipline ||
              finalResponse?.route?.discipline,
            agent: finalResponse?.agent || finalResponse?.route?.agent,
            extra: finalResponse?.extra,
            raw: finalResponse ?? undefined,
          },
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Erro ao comunicar com a API";
        setError(message);
        updateAssistant(assistantId, {
          content: `Erro: ${message}. Verifique se o backend está rodando em http://localhost:8000`,
          meta: { streaming: false, streamStatus: undefined },
        });
      } finally {
        setLoading(false);
      }
    },
    [updateAssistant]
  );

  return (
    <>
      <header className="shrink-0 border-b border-slate-800/80 px-6 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-white">Chat IA</h1>
            <p className="text-sm text-slate-500">
              Intent Layer → streaming em tempo real → agentes especializados
            </p>
          </div>
          {(activeModel || configuredModels) && (
            <div className="rounded-xl bg-slate-800/80 px-3 py-2 text-right ring-1 ring-slate-700">
              {activeModel && (
                <p className="text-xs font-medium text-emerald-300">
                  Modelo ativo: {activeModel}
                </p>
              )}
              {configuredModels && (
                <p className="mt-0.5 text-[11px] text-slate-500">{configuredModels}</p>
              )}
            </div>
          )}
        </div>
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
