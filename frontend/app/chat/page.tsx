"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import ChatBox from "@/components/ChatBox";
import MessageList from "@/components/MessageList";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import WorkspaceExpandButton, { WorkspaceCollapseStrip } from "@/components/WorkspaceExpandButton";
import { useChatStream } from "@/context/ChatStreamContext";
import { api } from "@/services/api";
import type { ChatMessage, ConversationDetail } from "@/types/api";

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
  const searchParams = useSearchParams();
  const urlConversationId = searchParams.get("c");
  const projectId = searchParams.get("project");

  const {
    messages,
    loading,
    error,
    activeModel,
    sendMessage,
    clearError,
    hydrateHistory,
    shouldSkipHistoryReload,
    conversationTitle,
  } = useChatStream();

  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (shouldSkipHistoryReload(urlConversationId)) {
      return;
    }

    if (!urlConversationId) {
      if (!loading) {
        hydrateHistory(null, [], null);
      }
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);
    api
      .conversation(urlConversationId)
      .then((conv) => {
        if (cancelled || shouldSkipHistoryReload(urlConversationId)) return;
        hydrateHistory(
          urlConversationId,
          messagesFromConversation(conv),
          conv.title || conv.input_text
        );
      })
      .catch(() => {
        if (!cancelled && !shouldSkipHistoryReload(urlConversationId)) {
          hydrateHistory(urlConversationId, [], null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [urlConversationId, hydrateHistory, shouldSkipHistoryReload, loading]);

  return (
    <>
      <WorkspaceCollapseStrip />
      <ShellHeader
        className="px-6"
        showModelsStatus
        trailing={
          <div className="flex min-w-0 max-w-full flex-wrap items-center justify-end gap-2">
            <Link
              href="/history"
              className="rounded-lg px-2 py-1 text-xs text-slate-400 ring-1 ring-slate-700 hover:text-white lg:hidden"
            >
              Histórico
            </Link>
            {activeModel ? (
              <div className="app-card min-w-0 max-w-full px-3 py-2">
                <p className="text-left text-xs font-medium leading-snug text-emerald-300 whitespace-normal break-words">
                  Modelo ativo: {activeModel}
                </p>
              </div>
            ) : null}
          </div>
        }
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <WorkspaceExpandButton />
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold gradient-text">
              {conversationTitle ? conversationTitle : "Chat IA"}
            </h1>
            <p className="truncate text-sm text-slate-500">
              {urlConversationId || messages.length > 0
                ? "Continuando conversa · multi-turn com histórico"
                : "Intent Layer → streaming em tempo real → agentes especializados"}
            </p>
          </div>
        </div>
      </ShellHeader>

      {error && (
        <div className="mx-6 mt-4 flex items-center justify-between gap-3 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
          <span>{error}</span>
          <button
            type="button"
            onClick={clearError}
            className="shrink-0 text-xs text-red-400 underline hover:text-red-200"
          >
            Fechar
          </button>
        </div>
      )}

      {loadingHistory && !loading ? (
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <LoadingSpinner label="Carregando conversa..." />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <MessageList messages={messages} loading={loading} />
          <ChatBox
            allowAttachments
            onSend={(text, options) =>
              sendMessage(text, {
                ...options,
                conversationId: urlConversationId,
                projectId,
              })
            }
            loading={loading}
          />
        </div>
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
