"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import WorkspaceExpandButton, { WorkspaceCollapseStrip } from "@/components/WorkspaceExpandButton";
import { useActionDialog } from "@/hooks/useActionDialog";
import { api } from "@/services/api";
import type { ProjectDetail, ProjectFileItem } from "@/types/api";
import { formatDate } from "@/lib/utils";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params.id);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const [uploadAccept, setUploadAccept] = useState(".pdf,.txt,.docx,.xlsx,.csv,.ifc,.dxf,.dwg");
  const [formatLabels, setFormatLabels] = useState("PDF, Word, Excel, CSV, TXT, IFC, DXF, DWG");
  const { confirm, ActionDialogHost } = useActionDialog();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProject(await api.project(projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar projeto");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api
      .projectFormats()
      .then((data) => {
        if (data.accept) setUploadAccept(data.accept);
        if (data.formats?.length) {
          setFormatLabels(data.formats.map((f) => f.label).join(", "));
        }
      })
      .catch(() => {
        /* fallback estático acima */
      });
  }, []);

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setError(null);
    setUploadNotice(null);
    try {
      const result = await api.uploadProjectFiles(projectId, Array.from(files));
      const indexed = result.indexing?.filter((r) => r.status === "indexed").length ?? 0;
      const partial = result.indexing?.filter((r) => r.status === "indexed" && (r as { partial?: boolean }).partial) ?? [];
      const indexErrors = result.indexing?.filter((r) => r.status === "error") ?? [];
      const skipped = result.indexing?.filter((r) => r.status === "skipped") ?? [];

      if (indexErrors.length > 0) {
        const first = indexErrors[0] as { filename?: string; error?: string; hint?: string };
        setUploadNotice(
          `${result.uploaded} arquivo(s) salvo(s). ${indexed} indexado(s), ${indexErrors.length} com falha na indexação RAG` +
            (first.hint ? `. ${first.hint}` : "") +
            (first.error ? ` (${first.error})` : "") +
            " Use «Reindexar RAG» quando o Ollama estiver livre."
        );
      } else if (partial.length > 0) {
        setUploadNotice(
          `${result.uploaded} arquivo(s) salvo(s) · ${indexed} indexado(s) (indexação parcial em ${partial.length} arquivo(s)).`
        );
      } else if (skipped.length > 0 && indexed === 0) {
        setUploadNotice(
          `${result.uploaded} arquivo(s) salvo(s). Alguns formatos não são indexáveis para RAG — use PDF, DOCX, TXT, etc.`
        );
      } else if (indexed > 0) {
        setUploadNotice(`${result.uploaded} arquivo(s) enviado(s) · ${indexed} indexado(s) para RAG`);
      } else if (result.uploaded > 0) {
        setUploadNotice(`${result.uploaded} arquivo(s) enviado(s) com sucesso.`);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no upload");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleReindex = async () => {
    setUploading(true);
    setUploadNotice(null);
    try {
      const summary = await api.reindexProject(projectId) as {
        indexed?: number;
        skipped?: number;
        errors?: unknown[];
        total_chunks?: number;
      };
      const errCount = summary.errors?.length ?? 0;
      if (errCount > 0) {
        setUploadNotice(
          `Reindexação: ${summary.indexed ?? 0} ok, ${errCount} erro(s), ${summary.skipped ?? 0} ignorado(s). ` +
            "Se persistir, pare análises visuais/LLM e tente novamente."
        );
      } else {
        setUploadNotice(
          `RAG atualizado: ${summary.indexed ?? 0} arquivo(s), ${summary.total_chunks ?? 0} trecho(s) indexados.`
        );
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao reindexar");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFile = async (file: ProjectFileItem) => {
    const ok = await confirm({
      title: "Remover arquivo",
      message: `Remover «${file.filename}» do projeto? Esta ação não pode ser desfeita.`,
      confirmLabel: "Remover",
      destructive: true,
    });
    if (!ok) return;
    try {
      await api.deleteProjectFile(projectId, file.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao remover arquivo");
    }
  };

  const handleDeleteProject = async () => {
    const ok = await confirm({
      title: "Excluir projeto",
      message:
        "Excluir este projeto e todas as conversas vinculadas? Os arquivos enviados também serão removidos.",
      confirmLabel: "Excluir",
      destructive: true,
    });
    if (!ok) return;
    try {
      await api.deleteProject(projectId);
      router.push("/projects");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao excluir");
    }
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <LoadingSpinner label="Carregando projeto..." size="lg" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-red-300">
        {error || "Projeto não encontrado"}
      </div>
    );
  }

  return (
    <>
      <WorkspaceCollapseStrip />
      <ShellHeader
        className="px-6"
        showModelsStatus
        trailing={
          <div className="flex shrink-0 items-center gap-2">
            <Link
              href={`/chat?project=${project.id}`}
              className="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500"
            >
              Nova conversa
            </Link>
            <Link
              href={`/budget?project=${project.id}`}
              className="rounded-lg bg-violet-600/90 px-3 py-2 text-sm font-medium text-white hover:bg-violet-500"
            >
              Orçamento
            </Link>
            <Link
              href={`/projects/${project.id}/review`}
              className="rounded-lg bg-amber-600/90 px-3 py-2 text-sm font-medium text-white hover:bg-amber-500"
            >
              Revisão Técnica
            </Link>
            <Link
              href={`/projects/${project.id}/activity`}
              className="rounded-lg bg-slate-700/90 px-3 py-2 text-sm font-medium text-white hover:bg-slate-600"
            >
              Atividade
            </Link>
            <Link
              href={`/projects/${project.id}/vision`}
              className="rounded-lg bg-emerald-600/90 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              Análise Visual
            </Link>
            <Link
              href={`/projects/${project.id}/workflow`}
              className="rounded-lg bg-sky-600/90 px-3 py-2 text-sm font-medium text-white hover:bg-sky-500"
            >
              Workflow
            </Link>
            <button
              type="button"
              onClick={handleDeleteProject}
              className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-red-300 ring-1 ring-slate-700 hover:bg-slate-700"
            >
              Excluir
            </button>
          </div>
        }
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <WorkspaceExpandButton />
          <div className="min-w-0">
            <p className="text-xs text-slate-500">
              <Link href="/projects" className="hover:text-cyan-400">
                Projetos
              </Link>
              {" / "}
              {project.name}
            </p>
            <h1 className="truncate text-lg font-semibold text-white">{project.name}</h1>
            {project.description && (
              <p className="mt-0.5 truncate text-sm text-slate-400">{project.description}</p>
            )}
          </div>
        </div>
      </ShellHeader>

      {error && (
        <div className="mx-6 mt-4 rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-300 ring-1 ring-red-500/30">
          {error}
        </div>
      )}

      {uploadNotice && !error && (
        <div className="mx-6 mt-4 rounded-xl bg-amber-500/10 px-4 py-3 text-sm text-amber-200 ring-1 ring-amber-500/30">
          {uploadNotice}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-2">
          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-medium text-white">Conversas ({project.conversations.length})</h2>
            </div>
            {project.conversations.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhuma conversa neste projeto.</p>
            ) : (
              <ul className="space-y-2">
                {project.conversations.map((conv) => (
                  <li key={conv.id}>
                    <Link
                      href={`/chat?c=${conv.id}&project=${project.id}`}
                      className="block rounded-xl bg-slate-800/50 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800"
                    >
                      <p className="truncate font-medium">{conv.title || conv.input_text}</p>
                      <p className="text-xs text-slate-500">
                        {conv.message_count} msgs · {formatDate(conv.updated_at || conv.created_at)}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-medium text-white">Arquivos ({project.files.length})</h2>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={uploading}
                  onClick={handleReindex}
                  className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-slate-300 ring-1 ring-slate-700 hover:bg-slate-700 disabled:opacity-50"
                  title="Reindexar todos os arquivos suportados para RAG do projeto"
                >
                  Reindexar RAG
                </button>
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-cyan-300 ring-1 ring-slate-700 hover:bg-slate-700 disabled:opacity-50"
                >
                  {uploading ? "Enviando..." : "Upload arquivos"}
                </button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={uploadAccept}
                className="hidden"
                onChange={(e) => handleUpload(e.target.files)}
              />
            </div>
            <p className="mb-3 text-xs text-slate-500">
              Arquivos indexados automaticamente ({formatLabels}) e usados como contexto nas
              conversas deste projeto. DWG usa extração parcial — prefira PDF ou DXF para melhor
              resultado.
            </p>
            {project.files.length === 0 ? (
              <p className="text-sm text-slate-500">
                Envie documentos do empreendimento — memoriais, planilhas, laudos, plantas CAD/BIM,
                etc.
              </p>
            ) : (
              <ul className="space-y-2">
                {project.files.map((file) => (
                  <li
                    key={file.id}
                    className="flex items-center justify-between rounded-xl bg-slate-800/50 px-3 py-2 text-sm"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-slate-200">{file.filename}</p>
                      <p className="text-xs text-slate-500">
                        {file.size_bytes ? `${Math.round(file.size_bytes / 1024)} KB` : "—"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteFile(file)}
                      className="ml-2 text-xs text-red-400 hover:text-red-300"
                    >
                      Remover
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
      <ActionDialogHost />
    </>
  );
}
