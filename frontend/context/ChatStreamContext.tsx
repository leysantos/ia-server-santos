"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { flushSync } from "react-dom";
import { useRouter } from "next/navigation";
import { chatStream } from "@/services/api";
import type { ChatMessage, ChatResponse } from "@/types/api";
import { generateId } from "@/lib/utils";
import { useActivityOptional } from "@/context/ActivityContext";
import type { ChatSendOptions } from "@/components/ChatBox";

export interface ChatStreamSendParams extends ChatSendOptions {
  conversationId?: string | null;
  projectId?: string | null;
}

export interface ChatStreamSession {
  conversationId: string | null;
  projectId: string | null;
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  activeModel: string | null;
  /** Texto da última pergunta (banner). */
  lastPrompt: string | null;
  activityId: string | null;
}

const IDLE: ChatStreamSession = {
  conversationId: null,
  projectId: null,
  messages: [],
  loading: false,
  error: null,
  activeModel: null,
  lastPrompt: null,
  activityId: null,
};

interface ChatStreamContextValue extends ChatStreamSession {
  /** Inicia stream — sobrevive a navegação (sem AbortSignal). */
  sendMessage: (text: string, params: ChatStreamSendParams) => void;
  clearError: () => void;
  /** Histórico carregado do servidor quando não há stream ativo. */
  hydrateHistory: (
    conversationId: string | null,
    messages: ChatMessage[],
    title?: string | null
  ) => void;
  /** True se deve ignorar reload do servidor (stream em andamento nesta conversa). */
  shouldSkipHistoryReload: (conversationId: string | null) => boolean;
  conversationTitle: string | null;
}

const ChatStreamContext = createContext<ChatStreamContextValue | null>(null);

export function ChatStreamProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const activity = useActivityOptional();
  const [session, setSession] = useState<ChatStreamSession>(IDLE);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const runningRef = useRef(false);
  const streamRafRef = useRef<number | null>(null);
  const pendingContentRef = useRef<{ id: string; content: string; meta: ChatMessage["meta"] } | null>(
    null
  );
  const conversationIdRef = useRef<string | null>(null);

  const flushPendingContent = useCallback(() => {
    streamRafRef.current = null;
    const pending = pendingContentRef.current;
    if (!pending) return;
    flushSync(() => {
      setSession((prev) => ({
        ...prev,
        messages: prev.messages.map((msg) =>
          msg.id === pending.id ? { ...msg, content: pending.content, meta: pending.meta } : msg
        ),
      }));
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

  const updateAssistant = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setSession((prev) => ({
      ...prev,
      messages: prev.messages.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg)),
    }));
  }, []);

  const shouldSkipHistoryReload = useCallback(
    (_conversationId: string | null) => session.loading,
    [session.loading]
  );

  const hydrateHistory = useCallback(
    (conversationId: string | null, messages: ChatMessage[], title?: string | null) => {
      setConversationTitle(title ?? null);
      setSession((prev) => {
        if (prev.loading) return prev;
        conversationIdRef.current = conversationId;
        return {
          ...IDLE,
          conversationId,
          messages,
        };
      });
    },
    []
  );

  const clearError = useCallback(() => {
    setSession((prev) => ({ ...prev, error: null }));
  }, []);

  const sendMessage = useCallback(
    (text: string, params: ChatStreamSendParams) => {
      if (runningRef.current) return;
      runningRef.current = true;

      const userMessage: ChatMessage = { id: generateId(), role: "user", content: text };
      const assistantId = generateId();
      const assistantPlaceholder: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        meta: { streaming: true, streamStatus: "Analisando intenção..." },
      };

      const startConversationId = params.conversationId ?? conversationIdRef.current ?? null;
      conversationIdRef.current = startConversationId;

      const liveActivityId = `chat-${assistantId}`;
      activity?.pushActivity({
        id: liveActivityId,
        source: "chat",
        message: text.slice(0, 120),
        status: "running",
        phase: "intent",
        projectId: params.projectId ?? undefined,
      });

      setSession((prev) => ({
        conversationId: startConversationId,
        projectId: params.projectId ?? null,
        messages: [...prev.messages, userMessage, assistantPlaceholder],
        loading: true,
        error: null,
        activeModel: prev.activeModel,
        lastPrompt: text,
        activityId: liveActivityId,
      }));

      // Sem AbortSignal — navegar para /console ou outra rota NÃO cancela o fetch.
      void (async () => {
        try {
          let accumulated = "";
          let finalResponse: ChatResponse | null = null;
          let streamMeta: ChatMessage["meta"] = { streaming: true, streamStatus: "Conectando..." };

          for await (const event of chatStream({
            text,
            use_rag: params.useRag,
            persist: params.persist,
            conversation_id: conversationIdRef.current ?? undefined,
            project_id: params.projectId ?? undefined,
            llm_model: params.llmModel !== "auto" ? params.llmModel : undefined,
          })) {
            if (event.type === "status") {
              const message = String(event.data.message ?? "Processando...");
              const model = event.data.llm_model ? String(event.data.llm_model) : undefined;
              const stepAgent = event.data.step
                ? String((event.data.step as { agent?: string }).agent ?? "")
                : undefined;
              const stepDiscipline = event.data.step
                ? String((event.data.step as { discipline?: string }).discipline ?? "")
                : undefined;
              activity?.updateActivity(liveActivityId, {
                message,
                phase: stepDiscipline || stepAgent || "processing",
                agent: stepAgent,
                discipline: stepDiscipline,
              });
              streamMeta = {
                streaming: true,
                streamStatus: message,
                llmModel: model,
                discipline: stepDiscipline || streamMeta?.discipline,
                agent: stepAgent || streamMeta?.agent,
              };
              if (model) {
                setSession((prev) => ({ ...prev, activeModel: model }));
              }
              flushSync(() => updateAssistant(assistantId, { meta: streamMeta }));
            }

            if (event.type === "token") {
              const token = String(event.data.token ?? "");
              const model = event.data.llm_model ? String(event.data.llm_model) : undefined;
              if (model) {
                setSession((prev) => ({ ...prev, activeModel: model }));
              }
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
                conversationIdRef.current = finalResponse.conversation_id;
                setSession((prev) => ({
                  ...prev,
                  conversationId: finalResponse!.conversation_id ?? prev.conversationId,
                }));
                if (!startConversationId) {
                  const qs = new URLSearchParams({ c: finalResponse.conversation_id });
                  if (params.projectId) qs.set("project", params.projectId);
                  router.replace(`/chat?${qs.toString()}`);
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

          setSession((prev) => ({
            ...prev,
            loading: false,
            activeModel: finalModel ?? prev.activeModel,
            lastPrompt: null,
          }));

          activity?.updateActivity(liveActivityId, {
            status: "done",
            message: "Resposta concluída",
            agent: finalResponse?.agent || finalResponse?.route?.agent,
            discipline: finalResponse?.discipline || finalResponse?.route?.discipline,
          });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Erro ao comunicar com a API";
          activity?.updateActivity(liveActivityId, { status: "error", message });
          updateAssistant(assistantId, {
            content: `Erro: ${message}. Verifique se o backend está rodando em http://localhost:8000`,
            meta: { streaming: false, streamStatus: undefined },
          });
          setSession((prev) => ({
            ...prev,
            loading: false,
            error: message,
            lastPrompt: null,
          }));
        } finally {
          runningRef.current = false;
        }
      })();
    },
    [activity, router, scheduleContentUpdate, updateAssistant]
  );

  const value = useMemo(
    () => ({
      ...session,
      sendMessage,
      clearError,
      hydrateHistory,
      shouldSkipHistoryReload,
      conversationTitle,
    }),
    [
      session,
      sendMessage,
      clearError,
      hydrateHistory,
      shouldSkipHistoryReload,
      conversationTitle,
    ]
  );

  return <ChatStreamContext.Provider value={value}>{children}</ChatStreamContext.Provider>;
}

export function useChatStream() {
  const ctx = useContext(ChatStreamContext);
  if (!ctx) {
    throw new Error("useChatStream must be used within ChatStreamProvider");
  }
  return ctx;
}

export function useChatStreamOptional() {
  return useContext(ChatStreamContext);
}
