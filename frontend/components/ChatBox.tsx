"use client";

import { FormEvent, KeyboardEvent, useId, useRef, useState } from "react";
import { ShellFooter } from "@/components/ShellHeader";
import ModelSelector from "@/components/ModelSelector";
import { useLlmModelSelection } from "@/hooks/useLlmModel";
import {
  CHAT_ATTACHMENT_ACCEPT,
  CHAT_ATTACHMENT_MAX_FILES,
  CHAT_ATTACHMENT_MAX_MB,
  formatChatAttachmentSize,
} from "@/lib/chat-attachments";
import { cn } from "@/lib/utils";

export interface ChatSendOptions {
  useRag: boolean;
  persist: boolean;
  llmModel: string;
  files?: File[];
}

interface ChatBoxProps {
  onSend: (text: string, options: ChatSendOptions) => void;
  loading?: boolean;
  placeholder?: string;
  allowAttachments?: boolean;
}

export default function ChatBox({
  onSend,
  loading = false,
  placeholder = "Descreva seu problema de engenharia...",
  allowAttachments = true,
}: ChatBoxProps) {
  const [text, setText] = useState("");
  const [useRag, setUseRag] = useState(true);
  const [persist, setPersist] = useState(true);
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const { model, setModel } = useLlmModelSelection();
  const modelSelectId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const maxBytes = CHAT_ATTACHMENT_MAX_MB * 1024 * 1024;

  const addFiles = (incoming: FileList | null) => {
    if (!incoming?.length) return;
    setFileError(null);
    const next = [...files];
    for (const file of Array.from(incoming)) {
      if (next.length >= CHAT_ATTACHMENT_MAX_FILES) {
        setFileError(`Máximo de ${CHAT_ATTACHMENT_MAX_FILES} arquivos por mensagem.`);
        break;
      }
      if (file.size > maxBytes) {
        setFileError(`${file.name} excede ${CHAT_ATTACHMENT_MAX_MB} MB.`);
        continue;
      }
      if (next.some((f) => f.name === file.name && f.size === file.size)) continue;
      next.push(file);
    }
    setFiles(next);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setFileError(null);
  };

  const submit = () => {
    const trimmed = text.trim();
    const hasFiles = files.length > 0;
    if ((!trimmed && !hasFiles) || loading) return;

    const message =
      trimmed || (hasFiles ? "Analise os arquivos anexados e responda com base neles." : "");

    onSend(message, {
      useRag,
      persist,
      llmModel: model,
      files: hasFiles ? [...files] : undefined,
    });
    setText("");
    setFiles([]);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
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

  const canSend = Boolean(text.trim() || files.length) && !loading;

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

          {allowAttachments && files.length > 0 && (
            <ul className="flex flex-wrap gap-2 px-1">
              {files.map((file, index) => (
                <li
                  key={`${file.name}-${file.size}-${index}`}
                  className="flex max-w-full items-center gap-2 rounded-lg bg-slate-800/80 px-2.5 py-1.5 text-xs text-slate-300 ring-1 ring-slate-700"
                >
                  <span className="truncate" title={file.name}>
                    {file.name}
                  </span>
                  <span className="shrink-0 text-slate-500">{formatChatAttachmentSize(file.size)}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(index)}
                    className="shrink-0 text-slate-500 hover:text-red-300"
                    aria-label={`Remover ${file.name}`}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}

          {fileError && <p className="px-1 text-xs text-amber-300">{fileError}</p>}

          <div className="flex items-end gap-2 rounded-2xl border border-white/5 bg-surface-card p-2 focus-within:border-brand-500/40 focus-within:ring-1 focus-within:ring-brand-500/30">
            {allowAttachments && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept={CHAT_ATTACHMENT_ACCEPT}
                  className="hidden"
                  onChange={(e) => {
                    addFiles(e.target.files);
                    e.target.value = "";
                  }}
                />
                <button
                  type="button"
                  disabled={loading || files.length >= CHAT_ATTACHMENT_MAX_FILES}
                  onClick={() => fileInputRef.current?.click()}
                  className={cn(
                    "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-slate-400 transition",
                    "hover:bg-slate-800 hover:text-brand-300 disabled:opacity-40"
                  )}
                  aria-label="Anexar arquivos"
                  title="Anexar arquivos (PDF, planilha, imagem, CAD…)"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.75}
                      d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                    />
                  </svg>
                </button>
              </>
            )}
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={1}
              disabled={loading}
              className="max-h-40 min-h-[2.75rem] flex-1 resize-none bg-transparent px-1 py-2.5 text-sm leading-relaxed text-white placeholder:text-slate-500 focus:outline-none disabled:opacity-50 sm:px-3"
            />
            <button
              type="submit"
              disabled={!canSend}
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

          {allowAttachments && (
            <p className="text-center text-[11px] text-slate-600 sm:text-left">
              Anexe PDF, Word, Excel, imagens, CAD/BIM, código etc. — modo Auto escolhe o modelo conforme o
              tipo de arquivo.
            </p>
          )}

          <p className="text-center text-xs text-slate-600 sm:hidden">
            Enter envia · Shift+Enter nova linha
          </p>
        </div>
      </form>
    </ShellFooter>
  );
}
