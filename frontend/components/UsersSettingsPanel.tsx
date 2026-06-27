"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, formatApiError } from "@/services/api";
import type { AuthUser, ModulePermissionsMap, UserRoleDefinition } from "@/types/api";
import { useAuth } from "@/context/AuthContext";
import ActionDialog from "@/components/ActionDialog";
import {
  SYSTEM_MODULES,
  defaultModulePermissions,
  moduleAccessLabel,
  normalizeModulePermissions,
} from "@/lib/system-modules";
import { cn } from "@/lib/utils";

const CREATE_NEW_ROLE = "__create_new__";

function fieldClass() {
  return "w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30";
}

const emptyForm = {
  username: "",
  password: "",
  email: "",
  full_name: "",
  role: "dev_user",
  newRoleSlug: "",
  newRoleLabel: "",
  module_permissions: defaultModulePermissions(true),
};

type EditForm = {
  email: string;
  full_name: string;
  role: string;
  password: string;
  module_permissions: ModulePermissionsMap;
};

function editFormFromUser(user: AuthUser): EditForm {
  return {
    email: user.email ?? "",
    full_name: user.full_name ?? "",
    role: user.role,
    password: "",
    module_permissions: normalizeModulePermissions(user.module_permissions),
  };
}

function ModulePermissionsGrid({
  value,
  onChange,
  disabled,
}: {
  value: ModulePermissionsMap;
  onChange: (next: ModulePermissionsMap) => void;
  disabled?: boolean;
}) {
  const setFlag = (moduleId: string, key: "hidden" | "blocked", checked: boolean) => {
    const next = { ...value, [moduleId]: { ...value[moduleId], [key]: checked } };
    onChange(next);
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-white/10">
      <table className="w-full min-w-[520px] text-left text-sm">
        <thead>
          <tr className="border-b border-white/10 bg-slate-950/60 text-xs uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2 font-medium">Módulo</th>
            <th className="px-3 py-2 text-center font-medium">Oculto</th>
            <th className="px-3 py-2 text-center font-medium">Bloqueado</th>
            <th className="px-3 py-2 font-medium">Estado</th>
          </tr>
        </thead>
        <tbody>
          {SYSTEM_MODULES.map((mod) => {
            const perm = value[mod.id] ?? { hidden: false, blocked: false };
            return (
              <tr key={mod.id} className="border-b border-white/5 text-slate-200">
                <td className="px-3 py-2.5">
                  <p className="font-medium">{mod.label}</p>
                  <p className="text-xs text-slate-500">{mod.description}</p>
                </td>
                <td className="px-3 py-2.5 text-center">
                  <input
                    type="checkbox"
                    disabled={disabled}
                    checked={perm.hidden}
                    onChange={(e) => setFlag(mod.id, "hidden", e.target.checked)}
                    className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500"
                    aria-label={`${mod.label} oculto`}
                  />
                </td>
                <td className="px-3 py-2.5 text-center">
                  <input
                    type="checkbox"
                    disabled={disabled || perm.hidden}
                    checked={perm.blocked}
                    onChange={(e) => setFlag(mod.id, "blocked", e.target.checked)}
                    className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-amber-500"
                    aria-label={`${mod.label} bloqueado`}
                  />
                </td>
                <td className="px-3 py-2.5 text-xs text-slate-400">{moduleAccessLabel(perm)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="border-t border-white/5 px-3 py-2 text-[11px] text-slate-500">
        Oculto: não aparece no menu. Bloqueado (sem oculto): visível mas acesso negado.
      </p>
    </div>
  );
}

export default function UsersSettingsPanel() {
  const { isAdmin, user: currentUser } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [roles, setRoles] = useState<UserRoleDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(emptyForm);
  const [creatingNewRole, setCreatingNewRole] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingUser, setEditingUser] = useState<AuthUser | null>(null);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AuthUser | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [dialog, setDialog] = useState({ open: false, title: "", message: "" });
  const [mounted, setMounted] = useState(false);
  const rolesInitialized = useRef(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const load = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [usersRes, rolesRes] = await Promise.all([api.authUsers(), api.authRoles()]);
      setUsers(usersRes.users);
      setRoles(rolesRes.roles);
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    void load();
  }, [load]);

  const applyRolePermissions = (roleSlug: string) => {
    const role = roles.find((r) => r.slug === roleSlug);
    if (role) {
      setForm((f) => ({
        ...f,
        role: roleSlug,
        module_permissions: normalizeModulePermissions(role.module_permissions),
      }));
    }
  };

  const handleRoleSelect = (value: string) => {
    if (value === CREATE_NEW_ROLE) {
      setCreatingNewRole(true);
      setForm((f) => ({
        ...f,
        role: CREATE_NEW_ROLE,
        newRoleSlug: "",
        newRoleLabel: "",
        module_permissions: defaultModulePermissions(true),
      }));
      return;
    }
    setCreatingNewRole(false);
    setForm((f) => ({ ...f, role: value, newRoleSlug: "", newRoleLabel: "" }));
    applyRolePermissions(value);
  };

  useEffect(() => {
    if (roles.length === 0 || rolesInitialized.current || creatingNewRole) return;
    rolesInitialized.current = true;
    const role = roles.find((r) => r.slug === form.role);
    if (role) {
      setForm((f) => ({
        ...f,
        module_permissions: normalizeModulePermissions(role.module_permissions),
      }));
    }
  }, [roles, creatingNewRole, form.role]);

  const handleCreate = async () => {
    if (!form.username.trim() || !form.password) return;
    setSaving(true);
    try {
      let roleSlug = form.role;
      if (creatingNewRole) {
        if (!form.newRoleSlug.trim() || !form.newRoleLabel.trim()) {
          setDialog({
            open: true,
            title: "Tipo de usuário",
            message: "Informe identificador e nome do novo tipo.",
          });
          setSaving(false);
          return;
        }
        const created = await api.authCreateRole({
          slug: form.newRoleSlug.trim().toLowerCase(),
          label: form.newRoleLabel.trim(),
          module_permissions: form.module_permissions,
        });
        roleSlug = created.role.slug;
        setRoles((prev) => [...prev, created.role].sort((a, b) => a.label.localeCompare(b.label)));
        setCreatingNewRole(false);
      }

      await api.authCreateUser({
        username: form.username.trim(),
        password: form.password,
        email: form.email.trim() || undefined,
        full_name: form.full_name.trim() || undefined,
        role: roleSlug,
        module_permissions: roleSlug === "admin" ? undefined : form.module_permissions,
      });
      setForm(emptyForm);
      setCreatingNewRole(false);
      await load();
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao criar",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (user: AuthUser) => {
    setEditingUser(user);
    setEditForm(editFormFromUser(user));
  };

  const closeEdit = () => {
    if (editSaving) return;
    setEditingUser(null);
    setEditForm(null);
  };

  const handleEditRoleChange = (roleSlug: string) => {
    const role = roles.find((r) => r.slug === roleSlug);
    setEditForm((f) => {
      if (!f) return f;
      return {
        ...f,
        role: roleSlug,
        module_permissions: role
          ? normalizeModulePermissions(role.module_permissions)
          : f.module_permissions,
      };
    });
  };

  const handleSaveEdit = async () => {
    if (!editingUser || !editForm) return;
    setEditSaving(true);
    try {
      const body: Parameters<typeof api.authUpdateUser>[1] = {
        email: editForm.email.trim() || undefined,
        full_name: editForm.full_name.trim() || undefined,
        role: editForm.role,
      };
      if (editForm.password.trim()) {
        body.password = editForm.password;
      }
      if (editForm.role !== "admin") {
        body.module_permissions = editForm.module_permissions;
      }
      await api.authUpdateUser(editingUser.id, body);
      closeEdit();
      await load();
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao salvar",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setEditSaving(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.authDeactivateUser(deleteTarget.id);
      setDeleteTarget(null);
      await load();
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao excluir",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    } finally {
      setDeleting(false);
    }
  };

  const handleReactivate = async (user: AuthUser) => {
    try {
      await api.authUpdateUser(user.id, { is_active: true });
      await load();
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
      });
    }
  };

  if (!isAdmin) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-6 text-sm text-amber-100">
        Apenas administradores podem gerenciar usuários. Você está conectado como{" "}
        <strong>{currentUser?.username}</strong> ({currentUser?.role_label ?? currentUser?.role}).
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-white/10 bg-slate-900/40 p-6">
        <h2 className="text-lg font-medium text-slate-100">Novo usuário</h2>
        <p className="mt-1 text-sm text-slate-400">
          Cadastre membros da equipe, escolha ou crie um tipo de usuário e defina o acesso por módulo.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <input
            placeholder="Usuário"
            value={form.username}
            onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
            className={fieldClass()}
          />
          <input
            type="password"
            placeholder="Senha (mín. 6 caracteres)"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            className={fieldClass()}
          />
          <input
            placeholder="E-mail"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            className={fieldClass()}
          />
          <input
            placeholder="Nome completo"
            value={form.full_name}
            onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
            className={fieldClass()}
          />
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs text-slate-500">Tipo de usuário</label>
            <select
              value={creatingNewRole ? CREATE_NEW_ROLE : form.role}
              onChange={(e) => handleRoleSelect(e.target.value)}
              className={fieldClass()}
            >
              {roles.map((role) => (
                <option key={role.slug} value={role.slug}>
                  {role.label} ({role.slug})
                </option>
              ))}
              <option value={CREATE_NEW_ROLE}>➕ Cadastrar novo…</option>
            </select>
          </div>
          {creatingNewRole && (
            <>
              <input
                placeholder="Identificador (ex: engenheiro_civil)"
                value={form.newRoleSlug}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    newRoleSlug: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""),
                  }))
                }
                className={fieldClass()}
              />
              <input
                placeholder="Nome exibido (ex: Engenheiro Civil)"
                value={form.newRoleLabel}
                onChange={(e) => setForm((f) => ({ ...f, newRoleLabel: e.target.value }))}
                className={fieldClass()}
              />
            </>
          )}
        </div>

        <div className="mt-6">
          <h3 className="text-sm font-medium text-slate-200">Módulos do sistema</h3>
          <p className="mt-1 text-xs text-slate-500">
            {creatingNewRole
              ? "Defina o padrão de acesso do novo tipo. Você pode ajustar por usuário abaixo."
              : "Permissões do usuário — pré-preenchidas pelo tipo selecionado."}
          </p>
          <div className="mt-3">
            <ModulePermissionsGrid
              value={form.module_permissions}
              onChange={(module_permissions) => setForm((f) => ({ ...f, module_permissions }))}
              disabled={form.role === "admin" && !creatingNewRole}
            />
            {form.role === "admin" && !creatingNewRole && (
              <p className="mt-2 text-xs text-violet-300/80">
                Administradores têm acesso total — permissões por módulo não se aplicam.
              </p>
            )}
          </div>
        </div>

        <button
          type="button"
          disabled={saving}
          onClick={() => void handleCreate()}
          className="mt-4 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-60"
        >
          {saving ? "Salvando…" : creatingNewRole ? "Criar tipo e cadastrar usuário" : "Cadastrar usuário"}
        </button>
      </section>

      <section className="rounded-xl border border-white/10 bg-slate-900/40 p-6">
        <h2 className="text-lg font-medium text-slate-100">Usuários cadastrados</h2>
        {loading ? (
          <p className="mt-4 text-sm text-slate-400">Carregando…</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-4">Usuário</th>
                  <th className="py-2 pr-4">Nome</th>
                  <th className="py-2 pr-4">Tipo</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2">Ações</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b border-white/5 text-slate-200">
                    <td className="py-3 pr-4 font-medium">{user.username}</td>
                    <td className="py-3 pr-4 text-slate-400">{user.full_name || user.email || "—"}</td>
                    <td className="py-3 pr-4">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-xs",
                          user.role === "admin"
                            ? "bg-violet-500/20 text-violet-200"
                            : "bg-slate-700/50 text-slate-300"
                        )}
                      >
                        {user.role_label ?? user.role}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      {user.is_active ? (
                        <span className="text-emerald-400">Ativo</span>
                      ) : (
                        <span className="text-slate-500">Inativo</span>
                      )}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <button
                          type="button"
                          onClick={() => openEdit(user)}
                          className="text-xs text-cyan-400 hover:text-cyan-300"
                        >
                          Editar
                        </button>
                        {user.id !== currentUser?.id && (
                          user.is_active ? (
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(user)}
                              className="text-xs text-red-400 hover:text-red-300"
                            >
                              Excluir
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => void handleReactivate(user)}
                              className="text-xs text-emerald-400 hover:text-emerald-300"
                            >
                              Reativar
                            </button>
                          )
                        )}
                        {user.id === currentUser?.id && (
                          <span className="text-xs text-slate-500">(você)</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {mounted &&
        editingUser &&
        editForm &&
        createPortal(
          <div
            className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
            role="presentation"
            onClick={closeEdit}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="edit-user-title"
              className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-slate-900 p-6 shadow-2xl ring-1 ring-slate-700/80"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 id="edit-user-title" className="text-lg font-semibold text-white">
                Editar usuário — {editingUser.username}
              </h3>
              <p className="mt-1 text-sm text-slate-400">
                Atualize dados, tipo de acesso e permissões por módulo.
              </p>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-slate-500">E-mail</label>
                  <input
                    value={editForm.email}
                    onChange={(e) => setEditForm((f) => f && { ...f, email: e.target.value })}
                    className={fieldClass()}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Nome completo</label>
                  <input
                    value={editForm.full_name}
                    onChange={(e) => setEditForm((f) => f && { ...f, full_name: e.target.value })}
                    className={fieldClass()}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Nova senha (opcional)</label>
                  <input
                    type="password"
                    placeholder="Deixe em branco para manter"
                    value={editForm.password}
                    onChange={(e) => setEditForm((f) => f && { ...f, password: e.target.value })}
                    className={fieldClass()}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Tipo de usuário</label>
                  <select
                    value={editForm.role}
                    onChange={(e) => handleEditRoleChange(e.target.value)}
                    disabled={editingUser.id === currentUser?.id}
                    className={fieldClass()}
                  >
                    {roles.map((role) => (
                      <option key={role.slug} value={role.slug}>
                        {role.label} ({role.slug})
                      </option>
                    ))}
                  </select>
                  {editingUser.id === currentUser?.id && (
                    <p className="mt-1 text-xs text-slate-500">
                      Não é possível alterar o próprio tipo de usuário.
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-6">
                <h4 className="text-sm font-medium text-slate-200">Módulos do sistema</h4>
                <div className="mt-3">
                  <ModulePermissionsGrid
                    value={editForm.module_permissions}
                    onChange={(module_permissions) =>
                      setEditForm((f) => f && { ...f, module_permissions })
                    }
                    disabled={editForm.role === "admin"}
                  />
                  {editForm.role === "admin" && (
                    <p className="mt-2 text-xs text-violet-300/80">
                      Administradores têm acesso total — permissões por módulo não se aplicam.
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-6 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={closeEdit}
                  disabled={editSaving}
                  className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void handleSaveEdit()}
                  disabled={editSaving}
                  className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-60"
                >
                  {editSaving ? "Salvando…" : "Salvar alterações"}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

      <ActionDialog
        open={!!deleteTarget}
        title="Excluir usuário"
        message={
          deleteTarget
            ? `Desativar o usuário "${deleteTarget.username}"?\n\nEle não poderá mais fazer login. Você pode reativá-lo depois em Editar ou Reativar.`
            : ""
        }
        variant="confirm"
        destructive
        confirmLabel={deleting ? "Excluindo…" : "Excluir"}
        onConfirm={deleting ? undefined : () => void handleConfirmDelete()}
        onCancel={() => !deleting && setDeleteTarget(null)}
      />

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
      />
    </div>
  );
}
