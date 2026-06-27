/** Catálogo de módulos — espelho de backend/core/auth/system_modules.py */

export interface ModulePermission {
  hidden: boolean;
  blocked: boolean;
}

export interface SystemModule {
  id: string;
  label: string;
  description: string;
}

export const SYSTEM_MODULES: SystemModule[] = [
  { id: "chat", label: "Chat IA", description: "Assistente single-domain" },
  { id: "orchestrate", label: "Orquestrador", description: "Multi-disciplinar" },
  { id: "copilot", label: "Copilot", description: "Planejamento IA" },
  { id: "aed", label: "AED", description: "Design autônomo" },
  { id: "projects", label: "Projetos", description: "Workspace" },
  { id: "budget", label: "Orçamento", description: "Pricing Engine" },
  { id: "console", label: "Console", description: "Operações e GPU" },
  { id: "history", label: "Histórico", description: "Conversas salvas" },
  { id: "settings", label: "Configurações", description: "Administração" },
];

export type ModulePermissionsMap = Record<string, ModulePermission>;

export function defaultModulePermissions(fullAccess = true): ModulePermissionsMap {
  const perms: ModulePermissionsMap = {};
  for (const mod of SYSTEM_MODULES) {
    perms[mod.id] = fullAccess
      ? { hidden: false, blocked: false }
      : { hidden: false, blocked: true };
  }
  return perms;
}

export function normalizeModulePermissions(
  raw?: ModulePermissionsMap | null
): ModulePermissionsMap {
  const base = defaultModulePermissions(true);
  if (!raw) return base;
  for (const mod of SYSTEM_MODULES) {
    const entry = raw[mod.id];
    if (!entry) continue;
    base[mod.id] = { hidden: Boolean(entry.hidden), blocked: Boolean(entry.blocked) };
  }
  return base;
}

export function moduleAccessLabel(perm: ModulePermission): string {
  if (perm.hidden) return "Oculto";
  if (perm.blocked) return "Visível, bloqueado";
  return "Liberado";
}

/** Mapeia href do menu para id do módulo */
export function moduleIdFromPath(pathname: string): string | null {
  if (pathname === "/budget" || pathname.startsWith("/budget")) return "budget";
  for (const mod of SYSTEM_MODULES) {
    if (mod.id === "budget") continue;
    const href = mod.id === "settings" ? "/settings" : `/${mod.id}`;
    if (pathname === href || pathname.startsWith(`${href}/`)) return mod.id;
  }
  return null;
}

export function canNavigateModule(
  permissions: ModulePermissionsMap | undefined,
  moduleId: string,
  isAdmin: boolean
): { allowed: boolean; visible: boolean; blocked: boolean } {
  if (isAdmin) return { allowed: true, visible: true, blocked: false };
  const perm = permissions?.[moduleId] ?? { hidden: false, blocked: false };
  if (perm.hidden) return { allowed: false, visible: false, blocked: false };
  if (perm.blocked) return { allowed: false, visible: true, blocked: true };
  return { allowed: true, visible: true, blocked: false };
}
