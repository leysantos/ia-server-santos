"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import ShellHeader from "@/components/ShellHeader";
import { useWorkspaceShell } from "@/components/WorkspaceShellContext";
import { useActionDialog } from "@/hooks/useActionDialog";
import { api } from "@/services/api";
import type { ConversationSummary, ProjectSummary } from "@/types/api";
import { cn } from "@/lib/utils";

function truncate(text: string, max = 42) {
  const t = text.trim();
  return t.length <= max ? t : `${t.slice(0, max)}…`;
}

function ConversationItem({
  conv,
  active,
  onOpen,
  onRenamed,
  onDeleted,
}: {
  conv: ConversationSummary;
  active: boolean;
  onOpen: () => void;
  onRenamed: () => void;
  onDeleted: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(conv.title || conv.input_text);
  const { confirm, ActionDialogHost } = useActionDialog();

  const handleRename = async () => {
    const next = title.trim();
    if (!next) return;
    try {
      await api.updateConversation(conv.id, { title: next });
      setEditing(false);
      setMenuOpen(false);
      onRenamed();
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async () => {
    const ok = await confirm({
      title: "Excluir conversa",
      message: "Excluir esta conversa permanentemente? Todo o histórico de mensagens será perdido.",
      confirmLabel: "Excluir",
      destructive: true,
    });
    if (!ok) return;
    try {
      await api.deleteConversation(conv.id);
      setMenuOpen(false);
      onDeleted();
    } catch {
      /* ignore */
    }
  };

  return (
    <>
      <div className="group relative flex items-center gap-0.5">
      {editing ? (
        <div className="flex flex-1 gap-1 px-1">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="min-w-0 flex-1 rounded border border-slate-600 bg-slate-950 px-2 py-1 text-xs text-white focus:border-cyan-500 focus:outline-none"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRename();
              if (e.key === "Escape") setEditing(false);
            }}
            autoFocus
          />
          <button
            type="button"
            onClick={handleRename}
            className="rounded bg-cyan-600 px-2 text-xs text-white"
          >
            OK
          </button>
        </div>
      ) : (
        <>
          <button
            type="button"
            onClick={onOpen}
            className={cn(
              "min-w-0 flex-1 truncate rounded-lg px-2 py-1.5 text-left text-xs hover:bg-slate-800/60",
              active
                ? "bg-cyan-500/10 text-cyan-300 ring-1 ring-cyan-500/20"
                : "text-slate-400"
            )}
          >
            {truncate(conv.title || conv.input_text)}
          </button>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="rounded p-1 text-slate-600 opacity-0 hover:text-slate-300 group-hover:opacity-100"
            aria-label="Ações"
          >
            ⋮
          </button>
        </>
      )}
      {menuOpen && !editing && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
          <div className="absolute right-0 top-full z-20 mt-1 w-36 rounded-lg bg-slate-900 py-1 shadow-xl ring-1 ring-slate-700">
            <button
              type="button"
              className="block w-full px-3 py-1.5 text-left text-xs text-slate-300 hover:bg-slate-800"
              onClick={() => {
                setEditing(true);
                setMenuOpen(false);
              }}
            >
              Renomear
            </button>
            <button
              type="button"
              className="block w-full px-3 py-1.5 text-left text-xs text-red-400 hover:bg-slate-800"
              onClick={handleDelete}
            >
              Excluir
            </button>
          </div>
        </>
      )}
      </div>
      <ActionDialogHost />
    </>
  );
}

export default function WorkspacePanel() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toggle } = useWorkspaceShell();
  const activeConversationId = searchParams.get("c") ?? searchParams.get("id");
  const activeProjectId = searchParams.get("project");

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({});
  const [projectConversations, setProjectConversations] = useState<
    Record<string, ConversationSummary[]>
  >({});
  const [loading, setLoading] = useState(true);
  const [creatingProject, setCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{
    projects: ProjectSummary[];
    conversations: ConversationSummary[];
  } | null>(null);
  const [searching, setSearching] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [projRes, convRes] = await Promise.all([
        api.projects(30),
        api.conversations(30, undefined, true),
      ]);
      setProjects(projRes.items);
      setConversations(convRes.items);
      setProjectConversations({});
    } catch {
      setProjects([]);
      setConversations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, pathname]);

  useEffect(() => {
    if (activeProjectId) {
      setExpandedProjects((prev) => ({ ...prev, [activeProjectId]: true }));
      loadProjectConversations(activeProjectId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProjectId]);

  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 2) {
      setSearchResults(null);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await api.searchWorkspace(q, 25);
        setSearchResults({
          projects: res.projects,
          conversations: res.conversations,
        });
      } catch {
        setSearchResults({ projects: [], conversations: [] });
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const loadProjectConversations = async (projectId: string) => {
    try {
      const res = await api.conversations(50, projectId);
      setProjectConversations((prev) => ({ ...prev, [projectId]: res.items }));
    } catch {
      setProjectConversations((prev) => ({ ...prev, [projectId]: [] }));
    }
  };

  const toggleProject = async (projectId: string) => {
    const next = !expandedProjects[projectId];
    setExpandedProjects((prev) => ({ ...prev, [projectId]: next }));
    if (next) await loadProjectConversations(projectId);
  };

  const startNewChat = (projectId?: string) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project", projectId);
    router.push(`/chat${params.toString() ? `?${params}` : ""}`);
  };

  const openBudget = (projectId?: string) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project", projectId);
    router.push(`/budget${params.toString() ? `?${params}` : ""}`);
  };

  const openConversation = (conversationId: string, projectId?: string | null) => {
    const params = new URLSearchParams({ c: conversationId });
    if (projectId) params.set("project", projectId);
    router.push(`/chat?${params.toString()}`);
  };

  const handleCreateProject = async () => {
    const name = newProjectName.trim();
    if (!name) return;
    try {
      await api.createProject(name);
      setNewProjectName("");
      setCreatingProject(false);
      await refresh();
    } catch {
      /* ignore */
    }
  };

  const handleConversationDeleted = (convId: string) => {
    if (activeConversationId === convId) {
      router.push("/chat");
    }
    refresh();
  };

  const isSearchMode = searchQuery.trim().length >= 2;

  const filteredProjects = useMemo(() => {
    if (!isSearchMode || !searchResults) return projects;
    return searchResults.projects;
  }, [isSearchMode, searchResults, projects]);

  const filteredConversations = useMemo(() => {
    if (!isSearchMode || !searchResults) return conversations;
    return searchResults.conversations.filter((c) => !c.project_id);
  }, [isSearchMode, searchResults, conversations]);

  const showPanel = pathname === "/chat" || pathname.startsWith("/projects");
  if (!showPanel) return null;

  return (
    <aside className="flex h-full min-h-0 w-full flex-col border-r border-white/5 bg-surface/95 backdrop-blur-xl">
      <ShellHeader innerClassName="flex-col justify-center gap-2.5 py-3">
        <div className="flex w-full items-center gap-2">
          <button
            type="button"
            onClick={() => startNewChat(activeProjectId ?? undefined)}
            className="flex min-h-[2.5rem] flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 px-3 text-sm font-medium text-white shadow-brand-sm transition hover:bg-brand-500"
          >
            <span className="text-base leading-none">+</span>
            Nova conversa
          </button>
          <button
            type="button"
            onClick={() => openBudget(activeProjectId ?? undefined)}
            className="flex min-h-[2.5rem] shrink-0 items-center justify-center rounded-xl border border-white/5 bg-surface-card px-3 text-sm text-slate-300 transition hover:bg-surface-elevated"
            title="Orçamento do projeto"
          >
            ₢
          </button>
          <button
            type="button"
            onClick={toggle}
            className="panel-collapse-btn"
            title="Ocultar conversas"
            aria-label="Ocultar painel de conversas"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        </div>
        <div className="relative w-full">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Buscar conversas e projetos..."
            className="w-full rounded-xl border border-white/5 bg-surface-card py-2 pl-3 pr-8 text-sm text-white placeholder:text-slate-500 focus:border-brand-500/60 focus:outline-none focus:ring-1 focus:ring-brand-500/30"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              aria-label="Limpar busca"
            >
              ×
            </button>
          )}
        </div>
        {isSearchMode && (
          <p className="w-full text-[11px] text-slate-500">
            {searching
              ? "Buscando..."
              : `${(searchResults?.projects.length ?? 0) + (searchResults?.conversations.length ?? 0)} resultado(s)`}
          </p>
        )}
      </ShellHeader>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {!isSearchMode && (
          <>
            <div className="mb-2 flex items-center justify-between px-2 pt-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Projetos
              </p>
              <button
                type="button"
                onClick={() => setCreatingProject((v) => !v)}
                className="text-xs text-brand-400 hover:text-brand-300"
              >
                {creatingProject ? "Cancelar" : "+ Novo"}
              </button>
            </div>

            {creatingProject && (
              <div className="app-card mb-3 space-y-2 p-2">
                <input
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="Nome do projeto"
                  className="w-full rounded-lg border border-white/5 bg-surface px-2 py-1.5 text-sm text-white focus:border-brand-500 focus:outline-none"
                  onKeyDown={(e) => e.key === "Enter" && handleCreateProject()}
                />
                <button
                  type="button"
                  onClick={handleCreateProject}
                  className="w-full rounded-lg bg-slate-800 py-1.5 text-xs text-slate-200 hover:bg-slate-700"
                >
                  Criar projeto
                </button>
              </div>
            )}
          </>
        )}

        {loading && !isSearchMode ? (
          <p className="px-2 py-4 text-xs text-slate-500">Carregando...</p>
        ) : (
          <>
            {isSearchMode && filteredProjects.length > 0 && (
              <>
                <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Projetos
                </p>
                {filteredProjects.map((project) => (
                  <Link
                    key={project.id}
                    href={`/projects/${project.id}`}
                    className="mb-1 block truncate rounded-lg px-2 py-2 text-sm text-slate-300 hover:bg-slate-800/60"
                  >
                    📁 {project.name}
                  </Link>
                ))}
              </>
            )}

            {!isSearchMode &&
              filteredProjects.map((project) => (
                <div key={project.id} className="mb-1">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => toggleProject(project.id)}
                      className="rounded p-1 text-slate-500 hover:text-slate-300"
                      aria-label="Expandir projeto"
                    >
                      {expandedProjects[project.id] ? "▾" : "▸"}
                    </button>
                    <Link
                      href={`/projects/${project.id}`}
                      className={cn(
                        "min-w-0 flex-1 truncate rounded-lg px-2 py-1.5 text-sm hover:bg-slate-800/60",
                        activeProjectId === project.id ? "text-cyan-300" : "text-slate-300"
                      )}
                    >
                      📁 {project.name}
                    </Link>
                    <button
                      type="button"
                      onClick={() => startNewChat(project.id)}
                      className="rounded p-1 text-slate-500 hover:text-cyan-400"
                      title="Nova conversa no projeto"
                    >
                      +
                    </button>
                    <button
                      type="button"
                      onClick={() => openBudget(project.id)}
                      className="rounded p-1 text-slate-500 hover:text-violet-400"
                      title="Orçamento do projeto"
                    >
                      ₢
                    </button>
                  </div>
                  {expandedProjects[project.id] && (
                    <div className="ml-5 space-y-0.5 border-l border-slate-800 pl-2">
                      {(projectConversations[project.id] ?? []).length === 0 ? (
                        <p className="py-1 text-xs text-slate-600">Sem conversas</p>
                      ) : (
                        (projectConversations[project.id] ?? []).map((conv) => (
                          <ConversationItem
                            key={conv.id}
                            conv={conv}
                            active={activeConversationId === conv.id}
                            onOpen={() => openConversation(conv.id, project.id)}
                            onRenamed={refresh}
                            onDeleted={() => handleConversationDeleted(conv.id)}
                          />
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))}

            <p className="mb-2 mt-4 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {isSearchMode ? "Conversas" : "Conversas recentes"}
            </p>
            {filteredConversations.length === 0 ? (
              <p className="px-2 text-xs text-slate-600">
                {isSearchMode ? "Nenhuma conversa encontrada" : "Nenhuma conversa ainda"}
              </p>
            ) : (
              filteredConversations.map((conv) => (
                <ConversationItem
                  key={conv.id}
                  conv={conv}
                  active={activeConversationId === conv.id}
                  onOpen={() => openConversation(conv.id, conv.project_id)}
                  onRenamed={refresh}
                  onDeleted={() => handleConversationDeleted(conv.id)}
                />
              ))
            )}

            {isSearchMode &&
              (searchResults?.conversations ?? []).filter((c) => c.project_id).length > 0 && (
                <>
                  <p className="mb-2 mt-4 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Em projetos
                  </p>
                  {(searchResults?.conversations ?? [])
                    .filter((c) => c.project_id)
                    .map((conv) => (
                      <ConversationItem
                        key={conv.id}
                        conv={conv}
                        active={activeConversationId === conv.id}
                        onOpen={() => openConversation(conv.id, conv.project_id)}
                        onRenamed={refresh}
                        onDeleted={() => handleConversationDeleted(conv.id)}
                      />
                    ))}
                </>
              )}
          </>
        )}
      </div>
    </aside>
  );
}
