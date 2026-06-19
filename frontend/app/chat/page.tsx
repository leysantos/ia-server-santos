"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useRouter, useSearchParams } from "next/navigation";
import ChatBox from "@/components/ChatBox";
import MessageList from "@/components/MessageList";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import WorkspaceExpandButton, { WorkspaceCollapseStrip } from "@/components/WorkspaceExpandButton";
import { chatStream, api } from "@/services/api";
import type { ChatMessage, ChatResponse, ConversationDetail } from "@/types/api";
import { generateId } from "@/lib/utils";

function messagesFromConversation(conv: ConversationDetail): ChatMessage[] {
  if (conv.messages?.length) {
    return conv.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      meta: m.meta
        ? {
            discipline: m.meta.discipline as string | undefined,
            agent: m.meta.agent as string | undefined,
            llmModel: m.meta.llm_model as string | undefined,
            extra: m.meta.extra as Record<string, unknown> | undefined,
          }
        : undefined,
    }));
  }
  return [];
}

function ChatPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlConversationId = searchParams.get("c");
  const projectId = searchParams.get("project");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(urlConversationId);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [configuredModels, setConfiguredModels] = useState<string | null>(null);

  const streamRafRef = useRef<number | null>(null);
  const pendingContentRef = useRef<{ id: string; content: string; meta: ChatMessage["meta"] } | null>(null);
  const conversationIdRef = useRef<string | null>(urlConversationId);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  useEffect(() => {
    return () => {
      if (streamRafRef.current != null) cancelAnimationFrame(streamRafRef.current);
    };
  }, []);

  const flushPendingContent = useCallback(() => {
    streamRafRef.current = null;
    const pending = pendingContentRef.current;
    if (!pending) return;
    flushSync(() => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === pending.id ? { ...msg, content: pending.content, meta: pending.meta } : msg
        )
      );
    });
  }, []);

  const scheduleContentUpdate = useCallback(
    (id: string, content: string, meta: ChatMessage["meta"]) => {
      pendingContentRef.current = { id, content, meta };
      if (streamRafRef.current != null) return;
      streamRafRef.current = requestAnimationFrame(flushPendingContent);
    },
    [flushPendingContent]
  );

  useEffect(() => {
    api.health().then((health) => {
      if (health.models?.installed_llm) {
        setConfiguredModels(`WSL: ${health.models.installed_llm}`);
      } else if (health.installed_models?.length) {
        const llms = health.installed_models.filter((m) => !m.toLowerCase().includes("embed"));
        setConfiguredModels(`WSL: ${llms.map((m) => m.replace(/:latest$/, "")).join(" · ")}`);
      } else if (health.models) {
        setConfiguredModels(`chat: ${health.models.chat} · eng: ${health.models.engineering}`);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    setConversationId(urlConversationId);
    conversationIdRef.current = urlConversationId;

    if (!urlConversationId) {
      setMessages([]);
      setConversationTitle(null);
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);
    api
      .conversation(urlConversationId)
      .then((conv) => {
        if (cancelled) return;
        setConversationTitle(conv.title || conv.input_text);
        setMessages(messagesFromConversation(conv));
      })
      .catch(() => {
        if (!cancelled) {
          setMessages([]);
          setConversationTitle(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [urlConversationId]);

  const updateAssistant = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg)));
  }, []);

  const handleSend = useCallback(
    async (text: string, options: { useRag: boolean; persist: boolean }) => {
      const userMessage: ChatMessage = { id: generateId(), role: "user", content: text };
      const assistantId = generateId();
      const assistantPlaceholder: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        meta: { streaming: true, streamStatus: "Analisando intenção..." },
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      setLoading(true);
      setError(null);

      try {
        let accumulated = "";
        let finalResponse: ChatResponse | null = null;
        let streamMeta: ChatMessage["meta"] = { streaming: true, streamStatus: "Conectando..." };

        for await (const event of chatStream({
          text,
          use_rag: options.useRag,
          persist: options.persist,
          conversation_id: conversationIdRef.current ?? undefined,
          project_id: projectId ?? undefined,
        })) {
          if (event.type === "status") {
            const message = String(event.data.message ?? "Processando...");
            const model = event.data.llm_model ? String(event.data.llm_model) : undefined;
            if (model) setActiveModel(model);
            streamMeta = {
              streaming: true,
              streamStatus: message,
              llmModel: model,
              discipline: event.data.step
                ? String((event.data.step as { discipline?: string }).discipline ?? "")
                : streamMeta?.discipline,
              agent: event.data.step
                ? String((event.data.step as { agent?: string }).agent ?? "")
                : streamMeta?.agent,
            };
            flushSync(() => updateAssistant(assistantId, { meta: streamMeta }));
          }

          if (event.type === "token") {
            const token = String(event.data.token ?? "");
            const model = event.data.llm_model ? String(event.data.llm_model) : undefined;
            if (model) setActiveModel(model);
            if (token) accumulated += token;
            streamMeta = {
              streaming: true,
              streamStatus: undefined,
              llmModel: model ?? streamMeta?.llmModel,
              discipline: String(event.data.discipline ?? streamMeta?.discipline ?? ""),
              agent: String(event.data.agent ?? streamMeta?.agent ?? ""),
            };
            scheduleContentUpdate(assistantId, accumulated, streamMeta);
          }

          if (event.type === "done") {
            finalResponse = event.data as unknown as ChatResponse;
            accumulated = finalResponse.result || accumulated;
            if (finalResponse.conversation_id) {
              setConversationId(finalResponse.conversation_id);
              conversationIdRef.current = finalResponse.conversation_id;
              if (!urlConversationId) {
                const params = new URLSearchParams({ c: finalResponse.conversation_id });
                if (projectId) params.set("project", projectId);
                router.replace(`/chat?${params.toString()}`);
              }
            }
          }
        }

        if (streamRafRef.current != null) {
          cancelAnimationFrame(streamRafRef.current);
          streamRafRef.current = null;
        }
        pendingContentRef.current = null;

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
            discipline: finalResponse?.discipline || finalResponse?.route?.discipline,
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
    [updateAssistant, scheduleContentUpdate, projectId, router, urlConversationId]
  );

  return (
    <>
      <WorkspaceCollapseStrip />
      <ShellHeader className="px-6" innerClassName="justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <WorkspaceExpandButton />
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold text-white">
              {conversationTitle ? conversationTitle : "Chat IA"}
            </h1>
            <p className="truncate text-sm text-slate-500">
              {conversationId
                ? "Continuando conversa · multi-turn com histórico"
                : "Intent Layer → streaming em tempo real → agentes especializados"}
            </p>
          </div>
        </div>
        {(activeModel || configuredModels) && (
          <div className="hidden shrink-0 rounded-xl bg-slate-800/80 px-3 py-2 text-right ring-1 ring-slate-700/80 sm:block">
            {activeModel && (
              <p className="text-xs font-medium text-emerald-300">Modelo ativo: {activeModel}</p>
            )}
            {configuredModels && (
              <p className="mt-0.5 text-[11px] text-slate-500">{configuredModels}</p>
            )}
          </div>
        )}
      </ShellHeader>

      {error && (
        <div className="mx-6 mt-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
          {error}
        </div>
      )}

      {loadingHistory ? (
        <div className="flex flex-1 items-center justify-center">
          <LoadingSpinner label="Carregando conversa..." />
        </div>
      ) : (
        <>
          <MessageList messages={messages} loading={loading} />
          <ChatBox onSend={handleSend} loading={loading} />
        </>
      )}
    </>
  );
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center">
          <LoadingSpinner label="Iniciando chat..." />
        </div>
      }
    >
      <ChatPageContent />
    </Suspense>
  );
}
