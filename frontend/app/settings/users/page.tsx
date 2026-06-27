"use client";

import UsersSettingsPanel from "@/components/UsersSettingsPanel";

export default function SettingsUsersPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-auto p-6 md:p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-100">Usuários</h1>
        <p className="mt-1 text-sm text-slate-400">
          Cadastro de contas, tipos de usuário customizados e permissões por módulo (oculto / bloqueado).
        </p>
      </header>
      <UsersSettingsPanel />
    </div>
  );
}
