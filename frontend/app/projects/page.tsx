"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import WorkspaceExpandButton, { WorkspaceCollapseStrip } from "@/components/WorkspaceExpandButton";
import { api } from "@/services/api";
import type { ProjectSummary } from "@/types/api";
import { formatDate } from "@/lib/utils";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.projects(100);
      setProjects(res.items);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      await api.createProject(name.trim(), description.trim() || undefined);
      setName("");
      setDescription("");
      await load();
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <WorkspaceCollapseStrip />
      <ShellHeader className="px-6" innerClassName="gap-3" showModelsStatus>
        <WorkspaceExpandButton />
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-white">Projetos</h1>
          <p className="text-sm text-slate-500">
            Organize conversas e arquivos por empreendimento — estilo workspace ChatGPT
          </p>
        </div>
      </ShellHeader>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <form
            onSubmit={handleCreate}
            className="rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800"
          >
            <h2 className="mb-3 text-sm font-medium text-white">Novo projeto</h2>
            <div className="space-y-3">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex.: Edifício Comercial Centro"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
              />
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Descrição opcional"
                rows={2}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={creating || !name.trim()}
                className="rounded-xl bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
              >
                {creating ? "Criando..." : "Criar projeto"}
              </button>
            </div>
          </form>

          {loading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner label="Carregando projetos..." />
            </div>
          ) : projects.length === 0 ? (
            <p className="text-center text-sm text-slate-500">Nenhum projeto ainda.</p>
          ) : (
            <ul className="space-y-3">
              {projects.map((p) => (
                <li key={p.id}>
                  <Link
                    href={`/projects/${p.id}`}
                    className="block rounded-2xl bg-slate-900/60 p-4 ring-1 ring-slate-800 hover:ring-cyan-500/30"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium text-white">📁 {p.name}</p>
                        {p.description && (
                          <p className="mt-1 text-sm text-slate-400 line-clamp-2">{p.description}</p>
                        )}
                      </div>
                      <span className="shrink-0 text-xs text-slate-500">
                        {formatDate(p.updated_at || p.created_at)}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      {p.conversation_count} conversas · {p.file_count} arquivos
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}
