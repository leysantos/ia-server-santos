"use client";

import { useCallback, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type {
  KnowledgeIngestResponse,
  KnowledgeOptionsResponse,
} from "@/types/api";

const ACCEPT = ".pdf,.csv,.xlsx,.xls,.json,.md,.txt,.docx";

type PresetKey = "nbr" | "sinapi" | "tcpo" | "auto";

const PRESETS: Record<
  Exclude<PresetKey, "auto">,
  { label: string; contentType: string; discipline: string; indexBase: string }
> = {
  nbr: {
    label: "NBR",
    contentType: "nbrs",
    discipline: "ESTRUTURAL",
    indexBase: "nbr",
  },
  sinapi: {
    label: "SINAPI",
    contentType: "sinapi",
    discipline: "ORÇAMENTO",
    indexBase: "sinapi",
  },
  tcpo: {
    label: "TCPO",
    contentType: "tcpo",
    discipline: "ORÇAMENTO",
    indexBase: "tcpo",
  },
};

interface QueuedFile {
  id: string;
  file: File;
}

interface KnowledgeUploaderProps {
  options: KnowledgeOptionsResponse;
  onIngest: (formData: FormData) => Promise<KnowledgeIngestResponse>;
  onComplete?: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function KnowledgeUploader({
  options,
  onIngest,
  onComplete,
}: KnowledgeUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [queue, setQueue] = useState<QueuedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [preset, setPreset] = useState<PresetKey>("auto");
  const [contentType, setContentType] = useState("");
  const [discipline, setDiscipline] = useState("");
  const [force, setForce] = useState(false);
  const [autoIndex, setAutoIndex] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<KnowledgeIngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const addFiles = useCallback((fileList: FileList | File[]) => {
    const incoming = Array.from(fileList);
    setQueue((prev) => {
      const existing = new Set(prev.map((q) => `${q.file.name}-${q.file.size}`));
      const next = [...prev];
      for (const file of incoming) {
        const key = `${file.name}-${file.size}`;
        if (!existing.has(key)) {
          next.push({ id: crypto.randomUUID(), file });
          existing.add(key);
        }
      }
      return next;
    });
    setResult(null);
    setError(null);
  }, []);

  const removeFile = (id: string) => {
    setQueue((prev) => prev.filter((q) => q.id !== id));
  };

  const clearQueue = () => {
    setQueue([]);
    setResult(null);
  };

  const applyPreset = (key: PresetKey) => {
    setPreset(key);
    if (key === "auto") {
      setContentType("");
      setDiscipline("");
      return;
    }
    const p = PRESETS[key];
    setContentType(p.contentType);
    setDiscipline(p.discipline);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleUpload = async () => {
    if (queue.length === 0) return;

    setUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    for (const { file } of queue) {
      formData.append("files", file);
    }
    if (discipline) formData.append("discipline", discipline);
    if (contentType) formData.append("content_type", contentType);
    formData.append("force", String(force));
    formData.append("auto_index", String(autoIndex));
    if (preset !== "auto" && PRESETS[preset]) {
      formData.append("index_base", PRESETS[preset].indexBase);
    }

    try {
      const response = await onIngest(formData);
      setResult(response);
      if (response.ingested > 0) {
        setQueue([]);
      }
      onComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no upload");
    } finally {
      setUploading(false);
    }
  };

  const totalSize = queue.reduce((acc, q) => acc + q.file.size, 0);

  return (
    <div className="space-y-6">
      {/* Presets */}
      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          Atalho por base
        </p>
        <div className="flex flex-wrap gap-2">
          {(["auto", "nbr", "sinapi", "tcpo"] as PresetKey[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => applyPreset(key)}
              className={cn(
                "rounded-lg px-4 py-2 text-sm font-medium transition-all",
                preset === key
                  ? key === "nbr"
                    ? "bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/40"
                    : key === "sinapi"
                      ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40"
                      : key === "tcpo"
                        ? "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40"
                        : "bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/40"
                  : "bg-slate-800/80 text-slate-400 ring-1 ring-slate-700 hover:text-slate-200"
              )}
            >
              {key === "auto" ? "Automático" : PRESETS[key].label}
            </button>
          ))}
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all",
          dragOver
            ? "border-cyan-400 bg-cyan-500/10"
            : "border-slate-700 bg-slate-900/40 hover:border-slate-500 hover:bg-slate-900/60"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-800 ring-1 ring-slate-700">
          <svg className="h-7 w-7 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>
        <p className="text-base font-medium text-slate-200">
          Arraste arquivos ou clique para selecionar
        </p>
        <p className="mt-1 text-sm text-slate-500">
          PDF, CSV, Excel, JSON, MD, TXT, DOCX — múltiplos arquivos de uma vez
        </p>
      </div>

      {/* Metadata */}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-slate-400">
            Tipo de conteúdo
          </span>
          <select
            value={contentType}
            onChange={(e) => {
              setContentType(e.target.value);
              setPreset("auto");
            }}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
          >
            <option value="">Detectar automaticamente</option>
            {options.content_types.map((ct) => (
              <option key={ct.value} value={ct.value}>
                {ct.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-slate-400">
            Disciplina
          </span>
          <select
            value={discipline}
            onChange={(e) => {
              setDiscipline(e.target.value);
              setPreset("auto");
            }}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
          >
            <option value="">Detectar automaticamente</option>
            {options.disciplines.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex cursor-pointer items-center gap-2 text-slate-300">
          <input
            type="checkbox"
            checked={autoIndex}
            onChange={(e) => setAutoIndex(e.target.checked)}
            className="rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500/30"
          />
          Indexar FAISS após ingestão
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-slate-300">
          <input
            type="checkbox"
            checked={force}
            onChange={(e) => setForce(e.target.checked)}
            className="rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500/30"
          />
          Sobrescrever arquivos existentes
        </label>
      </div>

      {/* Queue */}
      {queue.length > 0 && (
        <div className="rounded-xl bg-slate-900/60 ring-1 ring-slate-800">
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
            <p className="text-sm font-medium text-slate-200">
              {queue.length} arquivo{queue.length !== 1 ? "s" : ""} na fila
              <span className="ml-2 text-slate-500">({formatBytes(totalSize)})</span>
            </p>
            <button
              type="button"
              onClick={clearQueue}
              className="text-xs text-slate-500 hover:text-red-400"
            >
              Limpar fila
            </button>
          </div>
          <ul className="max-h-48 divide-y divide-slate-800 overflow-y-auto">
            {queue.map(({ id, file }) => (
              <li key={id} className="flex items-center justify-between px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-slate-300">{file.name}</p>
                  <p className="text-xs text-slate-500">{formatBytes(file.size)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => removeFile(id)}
                  className="ml-3 shrink-0 rounded p-1 text-slate-500 hover:bg-slate-800 hover:text-red-400"
                  aria-label={`Remover ${file.name}`}
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleUpload}
          disabled={uploading || queue.length === 0}
          className="rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:from-cyan-500 hover:to-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading
            ? "Enviando e indexando…"
            : `Enviar ${queue.length > 0 ? queue.length : ""} arquivo${queue.length !== 1 ? "s" : ""}`}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-3 rounded-xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
          <div className="flex flex-wrap gap-4 text-sm">
            <span className="text-emerald-400">
              ✓ {result.ingested} ingerido{result.ingested !== 1 ? "s" : ""}
            </span>
            {result.skipped > 0 && (
              <span className="text-amber-400">⊘ {result.skipped} ignorado{result.skipped !== 1 ? "s" : ""}</span>
            )}
            {result.errors.length > 0 && (
              <span className="text-red-400">✗ {result.errors.length} erro{result.errors.length !== 1 ? "s" : ""}</span>
            )}
            {result.indexing && (
              <span className="text-cyan-400">
                ⚡{" "}
                {"status" in result.indexing && result.indexing.status === "scheduled"
                  ? (result.indexing.message as string) || "Indexação em background"
                  : `Indexação concluída${
                      "total_chunks" in result.indexing && result.indexing.total_chunks != null
                        ? ` — ${result.indexing.total_chunks} chunks`
                        : "indexed_chunks" in result.indexing && result.indexing.indexed_chunks != null
                          ? ` — ${result.indexing.indexed_chunks} chunks`
                          : ""
                    }`}
              </span>
            )}
          </div>
          {result.results.length > 0 && (
            <ul className="max-h-40 divide-y divide-slate-800 overflow-y-auto rounded-lg bg-slate-950/50">
              {result.results.map((r, i) => (
                <li key={i} className="flex items-center justify-between px-3 py-2 text-xs">
                  <span className="truncate text-slate-300">{r.filename}</span>
                  <span
                    className={cn(
                      "ml-2 shrink-0 rounded px-2 py-0.5 font-medium",
                      r.status === "copied"
                        ? "bg-emerald-500/15 text-emerald-400"
                        : r.status.startsWith("skipped")
                          ? "bg-amber-500/15 text-amber-400"
                          : "bg-slate-700 text-slate-400"
                    )}
                  >
                    {r.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
