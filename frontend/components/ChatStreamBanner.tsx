"use client";

import Link from "next/link";
import { useChatStreamOptional } from "@/context/ChatStreamContext";

/** Banner global — chat continua em background ao navegar para /console etc. */
export default function ChatStreamBanner() {
  const chat = useChatStreamOptional();

  if (!chat?.loading) {
    return null;
  }

  const streamingMsg = chat.messages.find((m) => m.meta?.streaming);
  const status =
    streamingMsg?.meta?.streamStatus ||
    (chat.activeModel ? `Modelo: ${chat.activeModel}` : "Gerando resposta…");
  const prompt = chat.lastPrompt?.slice(0, 80);

  const href = chat.conversationId
    ? `/chat?c=${chat.conversationId}${chat.projectId ? `&project=${chat.projectId}` : ""}`
    : "/chat";

  return (
    <div className="border-b border-cyan-500/20 bg-cyan-950/40 px-4 py-2">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 text-sm">
        <p className="min-w-0 text-cyan-200">
          <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
          Chat em andamento
          {prompt ? `: «${prompt}${chat.lastPrompt && chat.lastPrompt.length > 80 ? "…" : ""}»` : ""}
          {status ? ` — ${status}` : ""}
        </p>
        <Link
          href={href}
          className="shrink-0 rounded-lg bg-cyan-600/30 px-3 py-1 text-xs font-medium text-cyan-100 ring-1 ring-cyan-500/40 hover:bg-cyan-600/50"
        >
          Voltar ao chat
        </Link>
      </div>
    </div>
  );
}
